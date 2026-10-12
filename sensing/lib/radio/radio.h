#pragma once

class RssiHistogram {
public:
  void add(int rssi);
  void send(const char* key) const;

private:
  static constexpr int MIN_DBM = -100;
  static constexpr int STEP_DB = 10;
  static constexpr int BIN_COUNT = 8;

  static int toBin(int rssi);

  int counts_[BIN_COUNT] = {};
};

void handleScanFailure(const char* error);
