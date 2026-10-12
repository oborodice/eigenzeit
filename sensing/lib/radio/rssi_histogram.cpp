#include "rssi_histogram.h"

#include <Arduino.h>

#include "json_lines.h"

void RssiHistogram::add(int rssi) {
  counts_[toBin(rssi)]++;
}

void RssiHistogram::send(const char* key) const {
  sendIntArray(key, counts_, BIN_COUNT);
}

int RssiHistogram::toBin(int rssi) {
  // 区間は下端を含み上端を含まない
  int bin = (rssi - MIN_DBM) / STEP_DB;
  // 範囲外の値は両端の区間に含める
  return constrain(bin, 0, BIN_COUNT - 1);
}
