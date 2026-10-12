#include "json_lines.h"

#include <Arduino.h>

void sendIntArray(const char* key, const int* values, int count) {
  Serial.printf("{\"time_ms\": %lu, \"%s\": [", millis(), key);
  for (int i = 0; i < count; i++) {
    if (i > 0) Serial.print(", ");
    Serial.print(values[i]);
  }
  Serial.println("]}");
}

void sendError(const char* error) {
  Serial.printf("{\"time_ms\": %lu, \"error\": \"%s\"}\n", millis(), error);
}
