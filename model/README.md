# model

```bash
# CoreS3とSuperColliderから受信した値を、画面に表示しながら recordings/ に記録する(Ctrl+Cで終了)
# CoreS3は自動で見つけ、接続が切れても繋ぎ直して記録を続ける
$ uv run record.py

# record.pyと同じように記録しながら、10秒ごとにSuperColliderの各層の値を0〜1の乱数で選び直して鳴らし、鳴らした値も記録する(Ctrl+Cで終了)
$ uv run play_random.py
```

## 記録の形式

- 形式: JSON Lines(1行に1つのJSONオブジェクト)
- 全ての行に、次の2つを付ける
  - `received_at` : 受信したときのPCの時刻(UNIX時刻、秒)
  - `source` : 送り元(`sensing` 、 `audio` 、 `model` のどれか)
- `sensing` の行: CoreS3から届いた値をそのまま含める。形式は [sensing/README.md > 送信データ](../sensing/README.md#送信データ) を参照
- `audio` の行: SuperColliderから127.0.0.1:9000にOSCの `/mic` で届いた値をそのまま含める。形式は [audio/README.md > 送信するOSC](../audio/README.md#送信するosc) を参照
- `model` の行: play_random.pyが鳴らした値を含める。キーは値を送ったOSCのアドレスで、値の並びは [audio/README.md > 受信するOSC](../audio/README.md#受信するosc) を参照

```json
{"received_at": 1793186093.472, "source": "audio", "band_rel_db": [-23.1, ..., -41.8], "total_db": -54.6, "flatness": 0.0123, "onset_count": 0}
{"received_at": 1793186093.777, "source": "sensing", "time_ms": 126000, "co2_ppm": 612}
{"received_at": 1793186100.002, "source": "model", "/sines/1": [0.5526, 0.0143, 0.0169, 0.3967, 0.7708], "/sines/2": [0.0805, 0.8729, 0.5504, 0.8481, 0.624], "/clicks": [0.1652, 0.5558, 0.9442, 0.266], "/noise": [0.9185, 0.1665, 0.799]}
```
