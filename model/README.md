# model

```bash
# CoreS3から受信した値を、画面に表示しながら recordings/ に記録する(Ctrl+Cで終了)
# CoreS3は自動で見つけ、接続が切れても繋ぎ直して記録を続ける
$ uv run record.py
```

- 受信するデータの形式は [sensing/README.md > 送信データ](../sensing/README.md#送信データ) を参照
