import argparse
import os
import pickle
import random
import threading
from collections import deque
from pathlib import Path
from typing import NamedTuple, TextIO

import torch
from pythonosc.udp_client import SimpleUDPClient

from predictor import NetworkPredictor, element_types, flatten_inputs, has_all_inputs
from record import Recording, record_while_playing
from sound import (
    AUDIO_ADDRESS,
    PLAY_SOURCE,
    PREVIOUS_AND_CURRENT_VALUE_COUNT,
    Sound,
    canonical_sound,
    flatten_previous_and_current,
    flatten_sound,
    random_sound,
    repeat_every_play_interval,
    send_sound,
    silent_sound,
)
from summarize_steps import summarize_inputs

# 区画の数。全ての区画で上達を比べられるようになるまで(区画の数 × 8回 × 10秒)、1時間かからない数にする
REGION_COUNT = 32
# 上達を測る、区画ごとのずれの数。その区画の少し前のこの回数分と、最近のこの回数分のずれの平均を比べる
# 1回ごとのずれの揺れを均しつつ、上達の変化に数分で気づける短さにする。記録を見て決め直す
PROGRESS_WINDOW = 4
# ときどきランダムな区画も試し、上達が尽きたと見ていた区画で世界が変わったことにも気づけるようにする
# 5回に1回は試し直す。記録を見て決め直す
EXPLORE_PROBABILITY = 0.2
# 区画の配置と選び方を、起動のたびに同じにする
SEED = 0
# 記録が読みやすいよう、ずれと上達は、比べたい差よりずっと細かい0.0001刻みにする
CURIOSITY_DECIMALS = 4
STATE_DIR = Path(__file__).parent / "state"
STATE_SUFFIX = ".pickle"


# 鳴らした刻みの区画と音と、その刻みの入力を予測したか
class _PlayedStep(NamedTuple):
    region: int
    sound: Sound
    predicted: bool


# 鳴らしている間に届いた行を、刻みごとに取り出せるよう溜めておく
class _BufferedRecording(Recording):
    def __init__(self, file: TextIO) -> None:
        super().__init__(file)
        self._rows: list[dict] = []
        self._rows_lock = threading.Lock()

    def _write_row(self, row: dict) -> None:
        super()._write_row(row)
        with self._rows_lock:
            self._rows.append(row)

    def take_rows(self) -> list[dict]:
        with self._rows_lock:
            rows, self._rows = self._rows, []
        return rows


# 値の空間に代表点を乱数で置き、どの値の組も一番近い代表点の区画に入れる
# 人間が決めるのは区画の数だけにし、どの値で分けるかは決めない
class _Regions:
    def __init__(self, count: int, rng: random.Random) -> None:
        self._rng = rng
        self._centers = torch.tensor([flatten_sound(canonical_sound(random_sound(rng))) for _ in range(count)])

    # 区画の中から一様に選ぶ。全体から一様に選び、その区画に入るまで選び直す
    def sample(self, region: int) -> Sound:
        while True:
            sound = canonical_sound(random_sound(self._rng))
            if self._region_of(sound) == region:
                return sound

    # どの値も0〜1で同じ大きさのため、重みを付けずにそのまま距離を測る
    def _region_of(self, sound: Sound) -> int:
        distances = ((self._centers - torch.tensor(flatten_sound(sound))) ** 2).sum(dim=1)
        return int(distances.argmin())


# 区画ごとに、少し前と最近のずれの平均の差を、上達として測る
class _LearningProgress:
    def __init__(self, region_count: int, window: int) -> None:
        self._window = window
        self._errors = [deque(maxlen=2 * window) for _ in range(region_count)]

    def add_error(self, region: int, error: float) -> None:
        self._errors[region].append(error)

    # 少し前と最近の両方のずれが揃っていれば、上達を比べられる
    def is_measurable(self, region: int) -> bool:
        errors = self._errors[region]
        return len(errors) == errors.maxlen

    # 比べられない区画の上達は0とする
    def progress(self, region: int) -> float:
        if not self.is_measurable(region):
            return 0.0
        errors = list(self._errors[region])
        return (sum(errors[: self._window]) - sum(errors[self._window :])) / self._window


# 学んだ状態。区画の代表点はSEEDから毎回同じ配置になるため、含めない
# 前の刻みの音も含めない。続きから始めた最初の1刻みは、前の音を無音として予測する(SuperColliderも起動し直していれば、実際に無音になっている)
class _LearnedState(NamedTuple):
    predictor: NetworkPredictor | None
    learning_progress: _LearningProgress
    rng_state: tuple


# 名前は記録を始めた時刻のため、名前の順で一番後のものが一番新しい
# ファイルの更新日時は、コピーしただけで変わることがあるため使わない
def _latest_state_path() -> Path | None:
    paths = sorted(STATE_DIR.glob(f"*{STATE_SUFFIX}"))
    return paths[-1] if paths else None


def _load_state(path: Path) -> _LearnedState:
    with path.open("rb") as file:
        return pickle.load(file)


# 書き込みの途中で電源が切れても前の状態が壊れないよう、別のファイルに書き終えてから置き換える
def _save_state(state: _LearnedState, path: Path) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    with temporary_path.open("wb") as file:
        pickle.dump(state, file)
    os.replace(temporary_path, path)


# 1刻みごとに、前の刻みの入力を観測して学び、次の区画を選んで鳴らす
class _CuriousPlayer:
    def __init__(self, recording: _BufferedRecording, state: _LearnedState | None) -> None:
        self._recording = recording
        self._client = SimpleUDPClient(*AUDIO_ADDRESS)
        self._rng = random.Random(SEED)
        self._regions = _Regions(REGION_COUNT, self._rng)
        self._step: _PlayedStep | None = None
        # 起動ごとに記録と同じ名前で保存する。前の起動の状態を上書きせず、どの記録のときの状態かが分かるようにする
        self._state_path = STATE_DIR / f"{recording.name}{STATE_SUFFIX}"
        if state is None:
            self._predictor: NetworkPredictor | None = None
            self._learning_progress = _LearningProgress(REGION_COUNT, PROGRESS_WINDOW)
        else:
            self._predictor = state.predictor
            self._learning_progress = state.learning_progress
            # 代表点を置いた後に戻し、区画の配置はSEEDのまま、選び方だけを続きからにする
            self._rng.setstate(state.rng_state)

    # __init__で戻す状態と対になる
    def _learned_state(self) -> _LearnedState:
        return _LearnedState(self._predictor, self._learning_progress, self._rng.getstate())

    def play_step(self) -> None:
        self._play_next(self._observe_and_learn())
        # 電源が急に切れても、直前の刻みまでに学んだことから続けられるよう、刻みごとに保存する
        _save_state(self._learned_state(), self._state_path)

    # 前の刻みの入力が揃っていれば返す。その入力を予測していれば、そのずれから学ぶ
    def _observe_and_learn(self) -> dict | None:
        rows = self._recording.take_rows()
        if self._step is None:
            return None
        inputs = summarize_inputs(rows)
        # CoreS3が抜けていたときなど、入力が揃わない刻みは学ばず、次の予測にも使わない
        if not has_all_inputs(inputs):
            return None
        if self._step.predicted:
            self._learn(inputs)
        return inputs

    # 予測とのずれから学び、そのずれで区画の上達を測り直す
    def _learn(self, inputs: dict) -> None:
        # 予測した刻みでは、予測のネットはもう作られている
        assert self._predictor is not None
        error = self._predictor.learn(flatten_inputs(inputs))
        self._learning_progress.add_error(self._step.region, error)
        progress = self._learning_progress.progress(self._step.region)
        self._recording.write(
            "curiosity",
            {
                "region": self._step.region,
                "error": round(error, CURIOSITY_DECIMALS),
                "progress": round(progress, CURIOSITY_DECIMALS),
            },
        )

    # 上達を比べられない区画があれば、先にそれを試す。どれも比べられれば、ときどきランダムな区画を、それ以外は上達が一番大きい区画を選ぶ
    # 上達が同じ区画どうしは、区画の番号で偏らないよう、ランダムに選ぶ
    def _choose_region(self) -> int:
        regions = range(REGION_COUNT)
        unmeasured = [region for region in regions if not self._learning_progress.is_measurable(region)]
        if unmeasured:
            return self._rng.choice(unmeasured)
        if self._rng.random() < EXPLORE_PROBABILITY:
            return self._rng.choice(regions)
        progresses = [self._learning_progress.progress(region) for region in regions]
        best = max(progresses)
        return self._rng.choice([region for region, progress in zip(regions, progresses) if progress == best])

    # 入力の値の数(赤外線の画素、マイクの帯域など)は、最初に揃った入力から分かるため、そのときにネットを作る
    def _predictor_for(self, inputs: dict) -> NetworkPredictor:
        if self._predictor is None:
            self._predictor = NetworkPredictor(element_types(inputs), PREVIOUS_AND_CURRENT_VALUE_COUNT, uses_sound=True)
        return self._predictor

    # 次の区画を選んで鳴らし、入力が揃っていれば、前の刻みの音とその音で、次の刻みの入力を予測しておく
    def _play_next(self, inputs: dict | None) -> None:
        region = self._choose_region()
        sound = self._regions.sample(region)
        send_sound(self._client, sound)
        self._recording.write(PLAY_SOURCE, sound)
        if inputs is not None:
            # まだ1回も鳴らしていなければ、SuperColliderは起動直後の無音のまま
            previous_sound = self._step.sound if self._step is not None else silent_sound()
            values = flatten_previous_and_current(previous_sound, sound)
            self._predictor_for(inputs).predict(flatten_inputs(inputs), values)
        self._step = _PlayedStep(region, sound, predicted=inputs is not None)


# 初めから学ぶ場合や、前の状態がない場合は、全ての区画を試すところから始める
def _play_curiously(recording: _BufferedRecording, fresh: bool) -> None:
    path = None if fresh else _latest_state_path()
    if path is None:
        print("Starting with nothing learned")
        state = None
    else:
        print(f"Resuming from {path}")
        state = _load_state(path)
    repeat_every_play_interval(_CuriousPlayer(recording, state).play_step)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", help="start with nothing learned instead of the latest state")
    fresh = parser.parse_args().fresh
    record_while_playing(_BufferedRecording, lambda recording: _play_curiously(recording, fresh))


if __name__ == "__main__":
    main()
