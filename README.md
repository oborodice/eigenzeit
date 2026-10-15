# Eigenzeiτ ─ 人工環世界音響生成

## 構成

- [センシング](sensing/README.md) : センサ値を取得し、USBシリアルで送信する(M5Stack CoreS3、PlatformIO)
- [AIモデル](model/README.md) : 入力を収集し、学習・予測する(Python)
- [オーディオ](audio/README.md) : 音を出力し、マイクの音から特徴量を抽出する(SuperCollider)
