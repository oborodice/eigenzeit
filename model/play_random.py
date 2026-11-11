import random
import threading
import time

from pythonosc.udp_client import SimpleUDPClient

from record import Recording, open_recording_file, record_inputs

# audio/main.scdが各層の値を受け取る先
AUDIO_ADDRESS = ("127.0.0.1", 57120)

# 層ごとのOSCのアドレスと値の数。並びと意味は audio/README.md の「受信するOSC」を参照
PARAM_COUNTS = {
    "/sines/1": 7,
    "/sines/2": 7,
    "/clicks": 4,
    "/noise": 3,
}
# SuperColliderの2秒の移りと残響の後に、電波の値が少なくとも1回ずつ届くだけの時間を残す
# 長くするほど試せる回数が減るため、この条件を満たす中で短めにする
PLAY_INTERVAL_SECONDS = 10
# 記録が読みやすいよう、聴き分けられる差よりずっと細かい0.0001刻みにする
VALUE_DECIMALS = 4


def random_values(count: int) -> list[float]:
    return [round(random.random(), VALUE_DECIMALS) for _ in range(count)]


# どの値の組み合わせも偏りなく試し、音と反応の関係を学ぶための記録を集めるため、一様な乱数で選ぶ
def choose_values() -> dict[str, list[float]]:
    return {address: random_values(count) for address, count in PARAM_COUNTS.items()}


def play_random_values(recording: Recording) -> None:
    client = SimpleUDPClient(*AUDIO_ADDRESS)
    next_play = time.monotonic()
    while True:
        values = choose_values()
        for address, layer_values in values.items():
            client.send_message(address, layer_values)
        recording.write("model", values)
        # 送るのにかかった時間を含めて、一定の間隔で選び直す
        next_play += PLAY_INTERVAL_SECONDS
        time.sleep(max(0, next_play - time.monotonic()))


def main() -> None:
    try:
        with open_recording_file() as file:
            recording = Recording(file)
            # 入力の記録は終わらずに続くため、別のスレッドで動かし、このスレッドで鳴らし続ける
            # Ctrl+Cで終えるとき、このスレッドの終わりを待たずに一緒に終わるようにする
            threading.Thread(target=record_inputs, args=(recording,), daemon=True).start()
            play_random_values(recording)
    # Ctrl+Cは止める通常の操作のため、エラーとして表示しない
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
