#include <M5CoreS3.h>

#include "radio.h"

void setup() {
  auto cfg = M5.config();
  CoreS3.begin(cfg);

  // CoreS3.begin()は初期設定ではシリアルを開始しないため、ここで開始する
  // USBシリアルでは通信速度の指定は使われないため、省略する
  Serial.begin();

  beginRadio();
}

void loop() {
  // スキャン自体に数秒かかるため、待ち時間は入れない
  scanRadio();
}
