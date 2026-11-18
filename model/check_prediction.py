import math
import sys
from pathlib import Path
from typing import NamedTuple

import torch

from predictor import NetworkPredictor, element_types, flatten_inputs, has_all_inputs
from sound import Sound, flatten_previous_and_current
from summarize_steps import played_values, read_recording, split_into_steps, summarize_inputs

# ずれを平均して表示する刻みの数
WINDOW_STEPS = 100
STEPS_COLUMN_WIDTH = 12
ERROR_COLUMN_WIDTH = 16
# 同じ記録から、いつも同じ結果になるようにする
SEED = 0


# 刻みtの入力、刻みtと刻みt+1で鳴らした値、刻みt+1の入力。どれも、刻みごとにまとめた辞書のまま持つ
class Pair(NamedTuple):
    current: dict
    previous_sound: Sound
    sound: Sound
    target: dict


# 記録を刻みに分け、刻みごとに鳴らした値と、まとめた入力の組にする
def read_steps(path: Path) -> list[tuple[Sound, dict]]:
    rows = read_recording(path)
    return [
        (played_values(play_row), summarize_inputs(observed_rows))
        for play_row, observed_rows in split_into_steps(rows)
    ]


# 届かなかった入力がある刻みは、値の並びが揃わないため使わない
def read_pairs(path: Path) -> tuple[list[Pair], int]:
    steps = read_steps(path)
    pairs = []
    skipped = 0
    for (previous_sound, current), (sound, target) in zip(steps, steps[1:]):
        if has_all_inputs(current) and has_all_inputs(target):
            pairs.append(Pair(current, previous_sound, sound, target))
        else:
            skipped += 1
    return pairs, skipped


# 次の刻みも今と同じと予測する。これに勝てなければ、学んだとは言えない
class UnchangedPredictor:
    def predict(self, current: list[float], _sound: list[float]) -> list[float]:
        return current

    def learn(self, _target: list[float]) -> None:
        pass


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
        sound = flatten_previous_and_current(pair.previous_sound, pair.sound)
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
    sound_size = len(flatten_previous_and_current(pairs[0].previous_sound, pairs[0].sound))
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
