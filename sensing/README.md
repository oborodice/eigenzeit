# sensing

```bash
# ポートの確認(Linuxでは /dev/ttyACM*)
$ ls /dev/cu.usbmodem*

# ビルド + 書き込み(失敗する場合はリセットボタンを2秒長押しし、ダウンロードモードにして再実行)
$ pio run -t upload --upload-port /dev/cu.usbmodem1101

# シリアルモニタ
$ pio device monitor --port /dev/cu.usbmodem1101
```
