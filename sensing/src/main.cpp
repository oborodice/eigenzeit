#include <M5CoreS3.h>

#include "radio.h"
#include "units.h"

// メモリには余裕があるため、どちらもArduinoのloopのタスクと同じ大きさにする
constexpr uint32_t TASK_STACK_BYTES = 8192;

// 電波のスキャンは数秒かかり、その間ほかのことができないため、ユニットを読むのとは別のタスクで繰り返す
static void radioTask(void*) {
  while (true) {
    scanRadio();
  }
}

static void unitsTask(void*) {
  while (true) {
    readUnits();
  }
}

void setup() {
  auto cfg = M5.config();
  CoreS3.begin(cfg);

  // CoreS3.begin()は初期設定ではシリアルを開始しないため、ここで開始する
  // USBシリアルでは通信速度の指定は使われないため、省略する
  Serial.begin();

  beginRadio();
  beginUnits();
  // コアを決めずに動かすと、シリアルに送る電波の行が途中で欠けたため、Arduinoのloopのタスクと同じコアに固定する
  xTaskCreatePinnedToCore(radioTask, "radio", TASK_STACK_BYTES, nullptr, 1, nullptr, ARDUINO_RUNNING_CORE);
  xTaskCreatePinnedToCore(unitsTask, "units", TASK_STACK_BYTES, nullptr, 1, nullptr, ARDUINO_RUNNING_CORE);
}

void loop() {
  // 繰り返す処理は上の2つのタスクで行うため、Arduinoのloopのタスクは使わない
  vTaskDelete(nullptr);
}
