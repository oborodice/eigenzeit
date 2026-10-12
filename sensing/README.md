# sensing

```bash
# ポートの確認(Linuxでは /dev/ttyACM*)
$ ls /dev/cu.usbmodem*

# ビルド + 書き込み(失敗する場合はリセットボタンを2秒長押しし、ダウンロードモードにして再実行)
$ pio run -t upload --upload-port /dev/cu.usbmodem1101

# シリアルモニタ
$ pio device monitor --port /dev/cu.usbmodem1101
```

## 送信データ

- 通信: USBシリアル
- 形式: JSON Lines(1行に1つのJSONオブジェクト、改行区切り)

```json
{"time_ms": 123456, "wifi_rssi_hist": [3, 4, 2, 2, 1, 0, 0, 0]}
{"time_ms": 125000, "ble_rssi_hist": [8, 6, 5, 3, 1, 0, 0, 0]}
{"time_ms": 126000, "error": "wifi_scan_failed"}
```

- `time_ms` : 起動からの経過時間(ミリ秒)
- `wifi_rssi_hist` : Wi-Fi基地局の電波の強さ(RSSI)の分布
- `ble_rssi_hist` : BLE機器の電波の強さ(RSSI)の分布
- `error` : 取得に失敗したときのエラーの種類(この行には値を含まない)
- 分布は、-100〜-20 dBmを10 dBごとの8区間に分け(範囲外の値は両端の区間に含める)、各区間に入った機器の数を弱い順に並べる
- Wi-FiとBLEは別の行として送信する
