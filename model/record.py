import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TextIO

import serial
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from serial.tools import list_ports

RECORDINGS_DIR = Path(__file__).parent / "recordings"
# 受け取った時刻は、CoreS3のtime_msと同じミリ秒まで残す
RECEIVED_AT_DECIMALS = 3

# ESP32-S3をUSBで直接繋いだときの、USBのベンダーIDとプロダクトID
# ポートの名前は繋ぎ方やOSで変わるため、これらでCoreS3を探す
CORES3_USB_VID = 0x303A
CORES3_USB_PID = 0x1001

RETRY_INTERVAL_SECONDS = 1

# audio/main.scdがマイクの特徴量を送る先
OSC_ADDRESS = ("127.0.0.1", 9000)


# シリアル、OSC、鳴らす処理など、複数のスレッドから書くため、1行を書き終えるまで他のスレッドが書かないようにする
class Recording:
    def __init__(self, file: TextIO) -> None:
        self._file = file
        self._lock = threading.Lock()

    # CoreS3とSuperColliderはそれぞれの起動からの時間しか持たないため、受け取った時刻を付けて並べられるようにする
    def write(self, source: str, values: dict) -> None:
        line = json.dumps({"received_at": round(time.time(), RECEIVED_AT_DECIMALS), "source": source, **values})
        with self._lock:
            print(line)
            self._file.write(line + "\n")
            # 電源が急に切れても、それまでの行が残るようにする
            self._file.flush()


def find_cores3_port() -> str | None:
    for port in list_ports.comports():
        if port.vid == CORES3_USB_VID and port.pid == CORES3_USB_PID:
            return port.device
    return None


def wait_for_cores3_port() -> str:
    port = find_cores3_port()
    if port is None:
        print("Waiting for CoreS3")
    while port is None:
        time.sleep(RETRY_INTERVAL_SECONDS)
        port = find_cores3_port()
    return port


def parse_json_line(line: str) -> dict | None:
    try:
        values = json.loads(line)
    except json.JSONDecodeError:
        return None
    # 行の途中の「42」のような断片も、JSONとしては読めてしまうため、オブジェクトだけを受け付ける
    return values if isinstance(values, dict) else None


def record_serial(port: str, recording: Recording) -> None:
    with serial.Serial(port) as connection:
        print(f"Connected to {port}")
        for raw in connection:
            values = parse_json_line(raw.decode(errors="replace").strip())
            # 接続した瞬間は行の途中から読み始めることがあるため、JSONとして読めない行は記録しない
            if values is None:
                continue
            recording.write("sensing", values)


# 展示中にケーブルが抜けたりCoreS3がリセットされたりしても、繋ぎ直して記録を続ける
def record_serial_with_reconnect(recording: Recording) -> None:
    while True:
        port = wait_for_cores3_port()
        try:
            record_serial(port, recording)
        # 切断とポートを開けない場合のどちらも、この例外になるため、内容を表示して区別できるようにする
        except serial.SerialException as error:
            print(f"Serial error: {error}")
            # ポートを開けない状態が続いたときに空回りしないよう、待ってから探し直す
            time.sleep(RETRY_INTERVAL_SECONDS)


def record_mic_message(recording: Recording, line: str) -> None:
    values = parse_json_line(line)
    if values is None:
        print(f"Invalid mic message: {line}")
        return
    recording.write("audio", values)


# OSCはUDPで接続が要らないため、シリアルと違って繋ぎ直す必要はなく、SuperColliderが後から起動しても届き始める
def record_mic_in_background(recording: Recording) -> None:
    dispatcher = Dispatcher()
    dispatcher.map("/mic", lambda _address, line: record_mic_message(recording, line))
    server = BlockingOSCUDPServer(OSC_ADDRESS, dispatcher)
    print(f"Listening for OSC on {OSC_ADDRESS[0]}:{OSC_ADDRESS[1]}")
    # Ctrl+Cで記録を終えるとき、このスレッドの終わりを待たずに一緒に終わるようにする
    threading.Thread(target=server.serve_forever, daemon=True).start()


def open_recording_file() -> TextIO:
    path = RECORDINGS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    RECORDINGS_DIR.mkdir(exist_ok=True)
    print(f"Recording to {path}")
    return path.open("w", encoding="utf-8")


# シリアルの受け取りは終わらずに続くため、マイクは先に別のスレッドで受け取り始める
def record_inputs(recording: Recording) -> None:
    record_mic_in_background(recording)
    record_serial_with_reconnect(recording)


def main() -> None:
    try:
        with open_recording_file() as file:
            record_inputs(Recording(file))
    # Ctrl+Cは記録を終える通常の操作のため、エラーとして表示しない
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
