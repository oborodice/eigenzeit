# model

```bash
# CoreS3とSuperColliderから受信した値を、画面に表示しながら recordings/ に記録する(Ctrl+Cで終了)
# CoreS3は自動で見つけ、接続が切れても繋ぎ直して記録を続ける
$ uv run record.py
```

## 記録の形式

- 形式: JSON Lines(1行に1つのJSONオブジェクト)
- 全ての行に、次の2つを付ける
  - `received_at` : 受信したときのPCの時刻(UNIX時刻、秒)
  - `source` : 送り元(`sensing` か `audio`)
- `sensing` の行: CoreS3から届いた値をそのまま含める。形式は [sensing/README.md > 送信データ](../sensing/README.md#送信データ) を参照
- `audio` の行: SuperColliderから127.0.0.1:9000にOSCの `/mic` で届いた値をそのまま含める。形式は [audio/README.md > 送信するOSC](../audio/README.md#送信するosc) を参照

```json
{"received_at": 1793186093.472, "source": "audio", "band_rel_db": [-23.1, ..., -41.8], "total_db": -54.6, "flatness": 0.0123, "onset_count": 0}
{"received_at": 1793186093.777, "source": "sensing", "time_ms": 126000, "co2_ppm": 612}
```
