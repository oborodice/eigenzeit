#include "co2.h"

#include <SensirionI2cScd4x.h>
#include <Wire.h>

static SensirionI2cScd4x sensor;

bool beginCo2() {
  sensor.begin(Wire, SCD40_I2C_ADDR_62);
  // CoreS3だけがリセットされたとき、SCD40は前の測定を続けているため、止めて初期状態に戻してから始める
  // SCD40はwakeUpに応答を返さない仕様で、成功しても失敗が返るため、結果は見ない
  sensor.wakeUp();
  if (sensor.stopPeriodicMeasurement() != 0 || sensor.reinit() != 0) {
    return false;
  }
  // 5秒ごとに新しい値を出す
  return sensor.startPeriodicMeasurement() == 0;
}

Co2Reading readCo2(uint16_t& ppm) {
  bool ready;
  if (sensor.getDataReadyStatus(ready) != 0) {
    return Co2Reading::Failed;
  }
  if (!ready) {
    return Co2Reading::NotReady;
  }
  // 温度と湿度は鑑賞者の影響をほぼ受けないため、使わない
  float temperature;
  float humidity;
  if (sensor.readMeasurement(ppm, temperature, humidity) != 0) {
    return Co2Reading::Failed;
  }
  return Co2Reading::Ready;
}
