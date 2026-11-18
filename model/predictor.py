import math

import torch
from river import preprocessing
from torch import nn

from summarize_steps import INPUT_STATISTICS

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
# 大きなモデルは学ぶのが遅く、上達の変化が見えにくくなるため、隠れ層2つ、それぞれ64ユニットの小さな全結合のネットにする
HIDDEN_UNITS = 64
# Adamの標準の値。0.003では、ずれがやや大きくなった
LEARNING_RATE = 0.001


# まとめた入力のキーと、その入力の種類
def _input_keys() -> list[tuple[str, str]]:
    return [
        (f"{name}_{statistic}", INPUT_TYPES[name])
        for name, statistics in INPUT_STATISTICS.items()
        for statistic in statistics
    ]


def has_all_inputs(inputs: dict) -> bool:
    return all(key in inputs for key, _ in _input_keys())


# まとめた値には、配列のもの(帯域ごと、画素ごとなど)と1つの数のものがあるため、どちらも並びとして扱う
def _as_list(value: float | list[float]) -> list[float]:
    return value if isinstance(value, list) else [value]


def flatten_inputs(inputs: dict) -> list[float]:
    return [value for key, _ in _input_keys() for value in _as_list(inputs[key])]


# 並べ直した値の1つ1つが、どの種類の入力か
def element_types(inputs: dict) -> list[str]:
    return [input_type for key, input_type in _input_keys() for _ in _as_list(inputs[key])]


# 値が届くたびに、正規化を少しずつ更新する。値の数は変わらないため、並びの位置を名前にする
class _OnlineScaler:
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
class _InputTypeNetwork:
    def __init__(self, input_size: int, sound_size: int, predicts_change: bool) -> None:
        self._predicts_change = predicts_change
        self._scaler = _OnlineScaler()
        self._net = nn.Sequential(
            nn.Linear(input_size + sound_size, HIDDEN_UNITS),
            nn.ReLU(),
            nn.Linear(HIDDEN_UNITS, HIDDEN_UNITS),
            nn.ReLU(),
            nn.Linear(HIDDEN_UNITS, input_size),
        )
        self._optimizer = torch.optim.Adam(self._net.parameters(), lr=LEARNING_RATE)
        self._prediction: torch.Tensor | None = None

    def predict(self, current: list[float], scaled_sound: torch.Tensor) -> list[float]:
        scaled_current = self._scaler.learn_and_scale(current)
        self._prediction = self._net(torch.cat([scaled_current, scaled_sound]))
        if self._predicts_change:
            self._prediction = self._prediction + scaled_current
        return self._scaler.unscale(self._prediction.detach())

    # 直前のpredictで出した予測と比べて学び、学ぶ前のずれ(正規化した単位の二乗の平均)を返す
    def learn(self, target: list[float]) -> float:
        loss = ((self._prediction - self._scaler.scale(target)) ** 2).mean()
        self._optimizer.zero_grad()
        loss.backward()
        self._optimizer.step()
        return loss.item()


# 入力の種類ごとのネットに分けて予測し、全ての入力の並びに戻す
# 1つのネットで全てを予測すると、次の値の予測に役立たない他の種類の値が多く、鳴らした値の効果が埋もれて学べないため
# 鳴らした値も入力と同じく正規化する。0〜1のままでは、正規化した入力よりばらつきが小さく、効果を学びにくいため
class NetworkPredictor:
    def __init__(self, types: list[str], sound_size: int, uses_sound: bool) -> None:
        self._uses_sound = uses_sound
        self._sound_scaler = _OnlineScaler()
        self._networks: list[tuple[list[int], _InputTypeNetwork]] = []
        for input_type in sorted(set(types)):
            indices = [i for i, element_type in enumerate(types) if element_type == input_type]
            network = _InputTypeNetwork(
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

    # 種類ごとのずれを、種類どうし同じ重みで平均して返す
    def learn(self, target: list[float]) -> float:
        errors = [network.learn([target[i] for i in indices]) for indices, network in self._networks]
        return sum(errors) / len(errors)
