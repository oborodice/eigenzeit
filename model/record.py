import json
import time
from datetime import datetime
from pathlib import Path
from typing import TextIO

import serial
from serial.tools import list_ports

# ESP32-S3をUSBで直接繋いだときの、USBのベンダーIDとプロダクトID
# ポートの名前は繋ぎ方やOSで変わるため、これらでCoreS3を探す
CORES3_USB_VID = 0x303A
CORES3_USB_PID = 0x1001

RETRY_INTERVAL_SECONDS = 1

RECORDINGS_DIR = Path(__file__).parent / "recordings"


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


def is_json_line(line: str) -> bool:
    try:
        json.loads(line)
    except json.JSONDecodeError:
        return False
    return True


def record(port: str, file: TextIO) -> None:
    with serial.Serial(port) as connection:
        print(f"Connected to {port}")
        for raw in connection:
            line = raw.decode(errors="replace").strip()
            # 接続した瞬間は行の途中から読み始めることがあるため、JSONとして読めない行は記録しない
            if not is_json_line(line):
                continue
            print(line)
            file.write(line + "\n")
            # 電源が急に切れても、それまでの行が残るようにする
            file.flush()


# 展示中にケーブルが抜けたりCoreS3がリセットされたりしても、繋ぎ直して記録を続ける
def record_with_reconnect(file: TextIO) -> None:
    while True:
        port = wait_for_cores3_port()
        try:
            record(port, file)
        # 切断とポートを開けない場合のどちらも、この例外になるため、内容を表示して区別できるようにする
        except serial.SerialException as error:
            print(f"Serial error: {error}")
            # ポートを開けない状態が続いたときに空回りしないよう、待ってから探し直す
            time.sleep(RETRY_INTERVAL_SECONDS)


def main() -> None:
    path = RECORDINGS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    RECORDINGS_DIR.mkdir(exist_ok=True)
    print(f"Recording to {path}")
    try:
        with path.open("w", encoding="utf-8") as file:
            record_with_reconnect(file)
    # Ctrl+Cは記録を終える通常の操作のため、エラーとして表示しない
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
