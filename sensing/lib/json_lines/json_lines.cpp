#include "json_lines.h"

#include <Arduino.h>
#include <freertos/semphr.h>

// 電波とユニットのセンサは別々のタスクから送るため、1行を書き終えるまで他のタスクが書かないようにする
// 書く途中で他の行が割り込むと、受信側でJSONとして読めない行になる
class LineLock {
public:
  LineLock() { xSemaphoreTake(mutex(), portMAX_DELAY); }
  ~LineLock() { xSemaphoreGive(mutex()); }

private:
  static SemaphoreHandle_t mutex() {
    static SemaphoreHandle_t handle = xSemaphoreCreateMutex();
    return handle;
  }
};

static void beginLine(const char* key) {
  Serial.printf("{\"time_ms\": %lu, \"%s\": ", millis(), key);
}

void sendInt(const char* key, int value) {
  LineLock lock;
  beginLine(key);
  Serial.print(value);
  Serial.println("}");
}

template <typename PrintValue>
static void sendArray(const char* key, int count, PrintValue printValue) {
  LineLock lock;
  beginLine(key);
  Serial.print("[");
  for (int i = 0; i < count; i++) {
    if (i > 0) {
      Serial.print(", ");
    }
    printValue(i);
  }
  Serial.println("]}");
}

void sendIntArray(const char* key, const int* values, int count) {
  sendArray(key, count, [&](int i) { Serial.print(values[i]); });
}

void sendFloatArray(const char* key, const float* values, int count, int decimals) {
  sendArray(key, count, [&](int i) { Serial.print(values[i], decimals); });
}

void sendError(const char* error) {
  LineLock lock;
  beginLine("error");
  Serial.printf("\"%s\"}\n", error);
}
