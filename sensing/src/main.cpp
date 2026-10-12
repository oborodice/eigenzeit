#include <M5CoreS3.h>

#include "radio.h"

constexpr uint32_t SERIAL_BAUD_RATE = 115200;

void setup() {
  auto cfg = M5.config();
  CoreS3.begin(cfg);

  // CoreS3.begin()は初期設定ではシリアルを開始しないため、ここで開始する
  Serial.begin(SERIAL_BAUD_RATE);

  beginRadio();
}

void loop() {
  // スキャン自体に数秒かかるため、待ち時間は入れない
  scanRadio();
}
