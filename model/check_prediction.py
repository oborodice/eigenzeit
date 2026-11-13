import math
import sys
from pathlib import Path
from typing import NamedTuple

import torch
from river import preprocessing
from torch import nn

from summarize_steps import INPUT_STATISTICS, played_values, read_recording, split_into_steps, summarize_inputs

# 入力の名前ごとの種類
INPUT_TYPES = {
    "band_db": "mic",
    "total_db": "mic",
    "flatness": "mic",
    "onset_count": "mic",
    "thermal_c": "thermal",
    "wifi_rssi_hist": "radio",
    "ble_rssi_hist": "radio",
    "co2_ppm": "co2",
}
# 今の値からの変化を予測する種類。ほとんど変わらない値は、次も今と同じという予測が最も当たるため、変化だけを学ばせて、それより悪くなりにくくする
CHANGE_PREDICTED_TYPES = {"co2"}
# ずれを平均して表示する刻みの数
WINDOW_STEPS = 100
STEPS_COLUMN_WIDTH = 12
ERROR_COLUMN_WIDTH = 16
# 大きなモデルは学ぶのが遅く、上達の変化が見えにくくなるため、隠れ層2つ、それぞれ64ユニットの小さな全結合のネットにする
HIDDEN_UNITS = 64
# Adamの標準の値。0.003では、ずれがやや大きくなった(2026-11-13の記録)
LEARNING_RATE = 0.001
# 同じ記録から、いつも同じ結果になるようにする
SEED = 0


# 刻みtの入力、刻みt+1で鳴らした値、刻みt+1の入力。どれも、刻みごとにまとめた辞書のまま持つ
class Pair(NamedTuple):
    current: dict
    sound: dict
    target: dict


# まとめた入力のキーと、その入力の種類
def input_keys() -> list[tuple[str, str]]:
    return [
        (f"{name}_{statistic}", INPUT_TYPES[name])
        for name, statistics in INPUT_STATISTICS.items()
        for statistic in statistics
    ]


# 記録を刻みに分け、刻みごとに鳴らした値と、まとめた入力の組にする
def read_steps(path: Path) -> list[tuple[dict, dict]]:
    rows = read_recording(path)
    return [
        (played_values(play_row), summarize_inputs(observed_rows))
        for play_row, observed_rows in split_into_steps(rows)
    ]


def has_all_inputs(inputs: dict) -> bool:
    return all(key in inputs for key, _ in input_keys())


# 届かなかった入力がある刻みは、値の並びが揃わないため使わない
def read_pairs(path: Path) -> tuple[list[Pair], int]:
    steps = read_steps(path)
    pairs = []
    skipped = 0
    for (_, current), (sound, target) in zip(steps, steps[1:]):
        if has_all_inputs(current) and has_all_inputs(target):
            pairs.append(Pair(current, sound, target))
        else:
            skipped += 1
    return pairs, skipped


# まとめた値には、配列のもの(帯域ごと、画素ごとなど)と1つの数のものがあるため、どちらも並びとして扱う
def as_list(value: float | list[float]) -> list[float]:
    return value if isinstance(value, list) else [value]


def flatten_inputs(inputs: dict) -> list[float]:
    return [value for key, _ in input_keys() for value in as_list(inputs[key])]


# 並べ直した値の1つ1つが、どの種類の入力か
def element_types(inputs: dict) -> list[str]:
    return [input_type for key, input_type in input_keys() for _ in as_list(inputs[key])]


def flatten_sound(sound: dict) -> list[float]:
    return [value for address in sorted(sound) for value in sound[address]]


# 次の刻みも今と同じと予測する。これに勝てなければ、学んだとは言えない
class UnchangedPredictor:
    def predict(self, current: list[float], _sound: list[float]) -> list[float]:
        return current

    def learn(self, _target: list[float]) -> None:
        pass


# 展示と同じく、正規化を少しずつ更新しながら学ぶ。値の数は変わらないため、並びの位置を名前にする
class OnlineScaler:
    def __init__(self) -> None:
        self._scaler = preprocessing.StandardScaler()

    # 受け取った時点で正規化にも覚えさせてから、正規化した値を返す
    def learn_and_scale(self, values: list[float]) -> torch.Tensor:
        self._scaler.learn_one(dict(enumerate(values)))
        return self.scale(values)

    def scale(self, values: list[float]) -> torch.Tensor:
        scaled = self._scaler.transform_one(dict(enumerate(values)))
        return torch.tensor([scaled[i] for i in range(len(values))], dtype=torch.float32)

    def unscale(self, scaled: torch.Tensor) -> list[float]:
        return [
            value * math.sqrt(self._scaler.vars[i]) + self._scaler.means[i]
            for i, value in enumerate(scaled.tolist())
        ]


# 1つの種類の入力を、その種類の今の値(と鳴らした値)から、1刻みごとにその場で学んで予測する
class InputTypeNetwork:
    def __init__(self, input_size: int, sound_size: int, predicts_change: bool) -> None:
        self._predicts_change = predicts_change
        self._scaler = OnlineScaler()
        self._net = nn.Sequential(
            nn.Linear(input_size + sound_size, HIDDEN_UNITS),
            nn.ReLU(),
            nn.Linear(HIDDEN_UNITS, HIDDEN_UNITS),
            nn.ReLU(),
            nn.Linear(HIDDEN_UNITS, input_size),
        )
        self._optimizer = torch.optim.Adam(self._net.parameters(), lr=LEARNING_RATE)
        self._prediction = None

    def predict(self, current: list[float], scaled_sound: torch.Tensor) -> list[float]:
        scaled_current = self._scaler.learn_and_scale(current)
        self._prediction = self._net(torch.cat([scaled_current, scaled_sound]))
        if self._predicts_change:
            self._prediction = self._prediction + scaled_current
        return self._scaler.unscale(self._prediction.detach())

    # 直前のpredictで出した予測と比べて学ぶ
    def learn(self, target: list[float]) -> None:
        loss = ((self._prediction - self._scaler.scale(target)) ** 2).mean()
        self._optimizer.zero_grad()
        loss.backward()
        self._optimizer.step()


# 入力の種類ごとのネットに分けて予測し、全ての入力の並びに戻す
# 1つのネットで全てを予測すると、次の値の予測に役立たない他の種類の値が多く、鳴らした値の効果が埋もれて学べないため
# 鳴らした値も入力と同じく正規化する。0〜1のままでは、正規化した入力よりばらつきが小さく、効果を学びにくいため
class NetworkPredictor:
    def __init__(self, types: list[str], sound_size: int, uses_sound: bool) -> None:
        self._uses_sound = uses_sound
        self._sound_scaler = OnlineScaler()
        self._networks = []
        for input_type in sorted(set(types)):
            indices = [i for i, element_type in enumerate(types) if element_type == input_type]
            network = InputTypeNetwork(
                len(indices), sound_size if uses_sound else 0, input_type in CHANGE_PREDICTED_TYPES
            )
            self._networks.append((indices, network))
        self._input_size = len(types)

    def predict(self, current: list[float], sound: list[float]) -> list[float]:
        scaled_sound = self._sound_scaler.learn_and_scale(sound) if self._uses_sound else torch.empty(0)
        predicted = [0.0] * self._input_size
        for indices, network in self._networks:
            values = network.predict([current[i] for i in indices], scaled_sound)
            for i, value in zip(indices, values):
                predicted[i] = value
        return predicted

    def learn(self, target: list[float]) -> None:
        for indices, network in self._networks:
            network.learn([target[i] for i in indices])


# 正規化は学ぶ間も更新され続け、何も学ばなくてもずれが減って見えることがあるため
# 比べるためのずれは、記録全体から一度だけ求めた、値ごとのばらつきで割って測る
def evaluation_scales(targets: list[list[float]]) -> list[float]:
    scales = []
    for values in zip(*targets):
        mean = sum(values) / len(values)
        std = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
        # 記録の間ずっと同じ値だった入力は、ずれも0になるため、割る値を1にしておく
        scales.append(std if std > 0 else 1)
    return scales


# 種類ごとに平均してから、種類どうしを同じ重みで平均し、値の数が多い赤外線(128個)がCO2(1個)などを埋もれさせないようにする
def errors_by_type(predicted: list[float], target: list[float], scales: list[float], types: list[str]) -> dict:
    squared_by_type = {}
    for value, true_value, scale, element_type in zip(predicted, target, scales, types):
        squared_by_type.setdefault(element_type, []).append(((value - true_value) / scale) ** 2)
    errors = {element_type: sum(squared) / len(squared) for element_type, squared in squared_by_type.items()}
    errors["total"] = sum(errors.values()) / len(errors)
    return errors


def run_predictors(pairs: list[Pair], predictors: dict, types: list[str]) -> dict[str, list[dict]]:
    targets = [flatten_inputs(pair.target) for pair in pairs]
    scales = evaluation_scales(targets)
    errors_by_predictor = {name: [] for name in predictors}
    for pair, target in zip(pairs, targets):
        current = flatten_inputs(pair.current)
        sound = flatten_sound(pair.sound)
        for name, predictor in predictors.items():
            # 学ぶ前に予測し、まだ見ていない刻みに対するずれを測る
            predicted = predictor.predict(current, sound)
            errors_by_predictor[name].append(errors_by_type(predicted, target, scales, types))
            predictor.learn(target)
    return errors_by_predictor


def print_windows(errors_by_predictor: dict[str, list[dict]], input_type: str) -> None:
    names = list(errors_by_predictor)
    print(f"\n{input_type}")
    print("steps".ljust(STEPS_COLUMN_WIDTH) + "".join(name.rjust(ERROR_COLUMN_WIDTH) for name in names))
    step_count = len(next(iter(errors_by_predictor.values())))
    for start in range(0, step_count, WINDOW_STEPS):
        end = min(start + WINDOW_STEPS, step_count)
        means = [
            sum(errors[input_type] for errors in errors_by_predictor[name][start:end]) / (end - start)
            for name in names
        ]
        row = f"{start}-{end - 1}".ljust(STEPS_COLUMN_WIDTH)
        print(row + "".join(f"{mean:{ERROR_COLUMN_WIDTH}.3f}" for mean in means))


def main() -> None:
    torch.manual_seed(SEED)
    pairs, skipped = read_pairs(Path(sys.argv[1]))
    types = element_types(pairs[0].current)
    sound_size = len(flatten_sound(pairs[0].sound))
    print(f"Pairs: {len(pairs)}, skipped: {skipped}, inputs: {len(types)}, sound values: {sound_size}")
    print("Mean squared error per value, in units of the value's spread over the whole recording")

    predictors = {
        "unchanged": UnchangedPredictor(),
        "without_sound": NetworkPredictor(types, sound_size, uses_sound=False),
        "with_sound": NetworkPredictor(types, sound_size, uses_sound=True),
    }
    errors_by_predictor = run_predictors(pairs, predictors, types)
    for input_type in ["total", *sorted(set(types))]:
        print_windows(errors_by_predictor, input_type)


if __name__ == "__main__":
    main()
