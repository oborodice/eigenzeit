import random
import time
from collections.abc import Callable

from pythonosc.udp_client import SimpleUDPClient

# audio/main.scdが各層の値を受け取る先
AUDIO_ADDRESS = ("127.0.0.1", 57120)
# 層の種類ごとのOSCのアドレスと値の数。値の並びは、audio/の各層のSynthDefの引数の順に揃える
_LAYER_PARAM_COUNTS = {
    "/sines": 8,
    "/clicks": 5,
    "/noise": 4,
}
# audio/main.scdが、どの種類の層も作る数。アドレスの末尾に1からの番号が付く
_SYNTHS_PER_LAYER = 2
# 鳴らした値を記録するときの送り元。記録を刻みに分けるときの目印にもなる
PLAY_SOURCE = "model"
# 刻みの中に、電波の値が少なくとも1回ずつ届く長さにする
# 長くするほど試せる回数が減るため、この条件を満たす中で短めにする
_PLAY_INTERVAL_SECONDS = 10
# 記録が読みやすいよう、聴き分けられる差よりずっと細かい0.0001刻みにする
_VALUE_DECIMALS = 4

# 層のOSCのアドレスごとの、鳴らす値の並び
type Sound = dict[str, list[float]]


def _synth_addresses(layer: str) -> list[str]:
    return [f"{layer}/{number}" for number in range(1, _SYNTHS_PER_LAYER + 1)]


# 鳴らせる全ての層のOSCのアドレスと値の数
_PARAM_COUNTS = {
    address: count for layer, count in _LAYER_PARAM_COUNTS.items() for address in _synth_addresses(layer)
}


# どの層のどの値も、0〜1から一様に選ぶ
def random_sound(rng: random.Random) -> Sound:
    return {
        address: [round(rng.random(), _VALUE_DECIMALS) for _ in range(count)] for address, count in _PARAM_COUNTS.items()
    }


# audio/main.scdの起動直後の状態。どの層も全ての値が0で、無音
def silent_sound() -> Sound:
    return {address: [0.0] * count for address, count in _PARAM_COUNTS.items()}


# 同じ種類の層は中身が同じため、入れ替えた組み合わせは同じ音になる
# 種類ごとに最初の値の順に並べ、同じ音が1通りに表されるようにする。並べても鳴らせる組み合わせは減らない
# 1通りに決まればどの値で並べてもよいため、最初の値(周波数や頻度)にする
def canonical_sound(sound: Sound) -> Sound:
    canonical = {}
    for layer in _LAYER_PARAM_COUNTS:
        addresses = _synth_addresses(layer)
        canonical.update(zip(addresses, sorted((sound[address] for address in addresses), key=lambda values: values[0])))
    return canonical


# 鳴らしたときの値と記録から読み直した値とで、層の順が違っても同じ並びになるよう、アドレスの順に並べる
def flatten_sound(sound: Sound) -> list[float]:
    return [value for address in sorted(sound) for value in sound[address]]


# 移る時間が長いと、刻みの間に鳴る音は、前の刻みの値から今の値へどこまで移ったかで決まるため、前の刻みの値と今の値を並べる
def flatten_previous_and_current(previous: Sound, current: Sound) -> list[float]:
    return flatten_sound(previous) + flatten_sound(current)


PREVIOUS_AND_CURRENT_VALUE_COUNT = len(flatten_previous_and_current(silent_sound(), silent_sound()))


def send_sound(client: SimpleUDPClient, sound: Sound) -> None:
    for address, layer_values in sound.items():
        client.send_message(address, layer_values)


def repeat_every_play_interval(play_once: Callable[[], None]) -> None:
    next_play = time.monotonic()
    while True:
        play_once()
        # 送るのにかかった時間を含めて、一定の間隔で選び直す
        next_play += _PLAY_INTERVAL_SECONDS
        time.sleep(max(0, next_play - time.monotonic()))
