#include "units.h"

#include <M5Unified.h>
#include <Wire.h>

#include "co2.h"
#include "json_lines.h"
#include "pahub.h"
#include "thermal.h"

constexpr uint8_t THERMAL_CHANNEL = 0;
constexpr uint8_t CO2_CHANNEL = 1;
// 赤外線は人の動きで秒単位に変わるため、1秒ごとに読む。CO2も同じ間隔で、新しい値が出ているかを確かめる
constexpr uint32_t READ_INTERVAL_MS = 1000;
// 赤外線はたまに読めないことがあり、リセットした直後の1回目は画素を書き換える途中の値になるため、1回の失敗では初期化しない
// 続けて読めないときだけ、ケーブルが抜けたとみなして初期化からやり直す
constexpr int READ_FAILURES_BEFORE_REINIT = 3;

struct Unit {
  uint8_t channel;
  bool (*begin)();
  // 読めなかったらfalseを返す
  bool (*readAndSend)();
  const char* initError;
  const char* readError;
  bool ready;
  int readFailures;
};

static bool readAndSendThermal() {
  float celsius[THERMAL_PIXEL_COUNT];
  if (!readThermal(celsius)) {
    return false;
  }
  // 1画素の細かさが0.25℃のため、小数第2位まで送る
  sendFloatArray("thermal_c", celsius, THERMAL_PIXEL_COUNT, 2);
  return true;
}

static bool readAndSendCo2() {
  uint16_t ppm;
  Co2Reading reading = readCo2(ppm);
  if (reading == Co2Reading::Ready) {
    sendInt("co2_ppm", ppm);
  }
  return reading != Co2Reading::Failed;
}

static Unit units[] = {
    {THERMAL_CHANNEL, beginThermal, readAndSendThermal, "thermal_init_failed", "thermal_read_failed", false, 0},
    {CO2_CHANNEL, beginCo2, readAndSendCo2, "co2_init_failed", "co2_read_failed", false, 0},
};

// ケーブルを挿し直したときに戻れるよう、初期化できていないユニットは読むたびに初期化を試す
static bool ensureReady(Unit& unit) {
  if (!unit.ready) {
    unit.ready = unit.begin();
    if (!unit.ready) {
      sendError(unit.initError);
    }
  }
  return unit.ready;
}

static void recordReadFailure(Unit& unit) {
  sendError(unit.readError);
  unit.readFailures++;
  if (unit.readFailures >= READ_FAILURES_BEFORE_REINIT) {
    unit.ready = false;
    unit.readFailures = 0;
  }
}

static void readUnit(Unit& unit) {
  if (!selectPaHubChannel(unit.channel)) {
    unit.ready = false;
    sendError("pahub_select_failed");
    return;
  }
  if (!ensureReady(unit)) {
    return;
  }
  if (unit.readAndSend()) {
    unit.readFailures = 0;
  } else {
    recordReadFailure(unit);
  }
}

static TickType_t lastReadTick;

void beginUnits() {
  // Groveポート(ポートA)のピンは、M5Unifiedが機種ごとに持っている値を使う
  Wire.begin(M5.Ex_I2C.getSDA(), M5.Ex_I2C.getSCL());
  lastReadTick = xTaskGetTickCount();
}

void readUnits() {
  for (Unit& unit : units) {
    readUnit(unit);
  }
  // 読むのにかかった時間を含めて、一定の間隔で読む
  vTaskDelayUntil(&lastReadTick, pdMS_TO_TICKS(READ_INTERVAL_MS));
}
