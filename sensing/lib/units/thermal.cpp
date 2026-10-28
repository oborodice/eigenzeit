#include "thermal.h"

#include <Arduino.h>
#include <Wire.h>

// AdafruitのAMG88xxライブラリは、読み込みに失敗しても結果を返さず、使わない画面表示のライブラリまで依存に含むため、レジスタを直接読む
constexpr uint8_t AMG8833_ADDRESS = 0x69;
constexpr uint8_t REG_POWER_CONTROL = 0x00;
constexpr uint8_t REG_RESET = 0x01;
constexpr uint8_t REG_FIRST_PIXEL = 0x80;
constexpr uint8_t POWER_NORMAL = 0x00;
constexpr uint8_t RESET_INITIAL = 0x3F;
// リセット後、最初の値が出るまで待つ時間
constexpr uint32_t RESET_SETTLE_MS = 100;
// 1画素は12ビットの2の補数で、1が0.25℃
constexpr float CELSIUS_PER_STEP = 0.25f;
constexpr int BYTES_PER_PIXEL = 2;
// 読み出しは原因の分からないまま1回ごとに15%ほど失敗し、続けて失敗することはまれなため、その場で読み直す
constexpr int READ_ATTEMPTS = 3;

static bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(AMG8833_ADDRESS);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

static bool readRegisters(uint8_t firstReg, uint8_t* bytes, int count) {
  Wire.beginTransmission(AMG8833_ADDRESS);
  Wire.write(firstReg);
  // 読み出しの前に通信を終えず、続けて読む(リピーテッドスタート)
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom(AMG8833_ADDRESS, static_cast<uint8_t>(count)) != count) {
    return false;
  }
  for (int i = 0; i < count; i++) {
    bytes[i] = Wire.read();
  }
  return true;
}

static bool readRegistersWithRetry(uint8_t firstReg, uint8_t* bytes, int count) {
  for (int attempt = 0; attempt < READ_ATTEMPTS; attempt++) {
    if (readRegisters(firstReg, bytes, count)) {
      return true;
    }
  }
  return false;
}

static float toCelsius(uint8_t low, uint8_t high) {
  int raw = ((high & 0x0F) << 8) | low;
  // 12ビット目が符号のため、負の温度に直す
  if (raw & 0x800) {
    raw -= 0x1000;
  }
  return raw * CELSIUS_PER_STEP;
}

bool beginThermal() {
  if (!writeRegister(REG_POWER_CONTROL, POWER_NORMAL) || !writeRegister(REG_RESET, RESET_INITIAL)) {
    return false;
  }
  delay(RESET_SETTLE_MS);
  return true;
}

bool readThermal(float (&celsius)[THERMAL_PIXEL_COUNT]) {
  uint8_t bytes[THERMAL_PIXEL_COUNT * BYTES_PER_PIXEL];
  if (!readRegistersWithRetry(REG_FIRST_PIXEL, bytes, sizeof(bytes))) {
    return false;
  }
  for (int i = 0; i < THERMAL_PIXEL_COUNT; i++) {
    celsius[i] = toCelsius(bytes[i * BYTES_PER_PIXEL], bytes[i * BYTES_PER_PIXEL + 1]);
  }
  return true;
}
