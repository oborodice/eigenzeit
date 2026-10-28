#include "pahub.h"

#include <Wire.h>

constexpr uint8_t PAHUB_ADDRESS = 0x70;

bool selectPaHubChannel(uint8_t channel) {
  Wire.beginTransmission(PAHUB_ADDRESS);
  // 選ぶチャンネルのビットだけを立てた1バイトを書くと、そのチャンネルだけが繋がる
  Wire.write(1 << channel);
  return Wire.endTransmission() == 0;
}
