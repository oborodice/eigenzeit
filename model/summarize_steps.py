import json
import statistics
import sys
from collections.abc import Callable
from pathlib import Path

# 音を選び直してから、audio/main.scdの2秒の移りと、残響が落ち着くまでの1秒ほどを待ってから観測する
# 移りの時間を変えたら見直す
SETTLE_SECONDS = 3

STATISTICS = {
    "mean": statistics.fmean,
    # 刻みの中に値が1つしか届かなくても計算できるよう、母標準偏差にする(標本標準偏差は値が2つ以上必要)
    "std": statistics.pstdev,
    "sum": sum,
}
# 入力の名前ごとに、どの統計でまとめるか
INPUT_STATISTICS = {
    # マイクは、1秒に数回揺れるうなりのような変化も捉えられるよう、平均に加えてばらつきも残す
    "band_db": ("mean", "std"),
    "total_db": ("mean", "std"),
    "flatness": ("mean", "std"),
    # 立ち上がりは、刻みの中で何回起きたかを数える
    "onset_count": ("sum",),
    # 赤外線は、平均で人がいるかを、ばらつきで人が動いたかを捉える
    "thermal_c": ("mean", "std"),
    # 電波は刻みによって1回か2回届くため、回数によらず比べられるよう平均にする
    "wifi_rssi_hist": ("mean",),
    "ble_rssi_hist": ("mean",),
    "co2_ppm": ("mean",),
}


def read_recording(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file]


# 鳴らした値と、その音が鳴っている間の行の組に分ける
# 最初に鳴らす前の行と、最後に鳴らした後の続きのない刻みは使わない
def split_into_steps(rows: list[dict]) -> list[tuple[dict, list[dict]]]:
    play_indices = [i for i, row in enumerate(rows) if row["source"] == "model"]
    steps = []
    for start, end in zip(play_indices, play_indices[1:]):
        play_row = rows[start]
        observe_from = play_row["received_at"] + SETTLE_SECONDS
        observed_rows = [row for row in rows[start + 1 : end] if row["received_at"] >= observe_from]
        steps.append((play_row, observed_rows))
    return steps


def played_values(play_row: dict) -> dict:
    return {key: value for key, value in play_row.items() if key not in ("received_at", "source")}


def summarize_elementwise(values: list, statistic: Callable[[list], float]) -> float | list[float]:
    if isinstance(values[0], list):
        return [statistic(list(element_values)) for element_values in zip(*values)]
    return statistic(values)


# 刻みの中で届かなかった入力は、まとめた値に含めない
def summarize_inputs(rows: list[dict]) -> dict:
    summary = {}
    for name, statistic_names in INPUT_STATISTICS.items():
        values = [row[name] for row in rows if name in row]
        if not values:
            continue
        for statistic_name in statistic_names:
            summary[f"{name}_{statistic_name}"] = summarize_elementwise(values, STATISTICS[statistic_name])
    return summary


def main() -> None:
    rows = read_recording(Path(sys.argv[1]))
    for play_row, observed_rows in split_into_steps(rows):
        step = {
            "played_at": play_row["received_at"],
            "sound": played_values(play_row),
            "inputs": summarize_inputs(observed_rows),
        }
        print(json.dumps(step))


if __name__ == "__main__":
    main()
