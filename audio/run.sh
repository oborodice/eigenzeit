#!/bin/sh
# main.scdを起動し、Ctrl+Cで止めたときも、録音したファイルを閉じてから終わる
# sclangはCtrl+Cを受けると、ファイルを閉じずにすぐ終わる。スクリプトから裏で起動したプログラムはCtrl+Cを無視するため、sclangと音を出すサーバーには届かず、このスクリプトだけが受け取る
sclang=/Applications/SuperCollider.app/Contents/MacOS/sclang
# sclangがOSCを受け取るポート(sclangの既定)。model/sound.pyのAUDIO_ADDRESSと同じ
sclang_port=57120

cd "$(dirname "$0")" || exit 1
"$sclang" main.scd &
sclang_pid=$!
# 止める合図は、値のないOSCの /quit 。アドレスと値の型の並びを、それぞれ4バイトの倍数になるよう0で埋める
trap 'printf "/quit\0\0\0,\0\0\0" | nc -u -w 1 127.0.0.1 "$sclang_port"' INT
# Ctrl+Cを受けると待つのが途中で終わるため、sclangが終わるまで待ち直す
while kill -0 "$sclang_pid" 2>/dev/null; do
	wait "$sclang_pid"
done
