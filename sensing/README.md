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
{"time_ms": 125500, "thermal_c": [24.25, 24.50, 24.00, ..., 31.75]}
{"time_ms": 126000, "co2_ppm": 612}
{"time_ms": 126500, "error": "wifi_scan_failed"}
```

- `time_ms` : 起動からの経過時間(ミリ秒)
- `wifi_rssi_hist` : Wi-Fi基地局の電波の強さ(RSSI)の分布
- `ble_rssi_hist` : BLE機器の電波の強さ(RSSI)の分布
- `thermal_c` : 赤外線アレイセンサ(AMG8833)の8×8画素の温度(℃、0.25℃刻み)。1行目の左から右へ、次の行へと64個を並べる
- `co2_ppm` : CO2の濃度(ppm)
- `error` : 取得に失敗したときのエラーの種類(この行には値を含まない)
- 分布は、-100〜-20 dBmを10 dBごとの8区間に分け(範囲外の値は両端の区間に含める)、各区間に入った機器の数を弱い順に並べる
- Wi-FiとBLEは別の行として送信する
- 赤外線は1秒ごとに送り、CO2は5秒ごとに出る新しい値を出るたびに送る
- PaHubのチャンネル0に赤外線(AMG8833)、チャンネル1にCO2(SCD40)を繋ぐ
