# audio

```bash
# 音を出すサーバーを起動し、OSCを待ち受ける(出力先はOSの既定の出力、Ctrl+Cで終了)
$ /Applications/SuperCollider.app/Contents/MacOS/sclang main.scd
```

## 受信するOSC

- 通信: UDP、ポート57120
- `/sine` : サイン波を鳴らす(起動直後は音量0で、無音)
  - 1つ目の値: 周波数(Hz、範囲外の値は20〜20000に収める)
  - 2つ目の値: 音量(範囲外の値は0〜1に収める)
