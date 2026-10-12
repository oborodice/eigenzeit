#include "ble_scan.h"

#include <Arduino.h>
#include <NimBLEDevice.h>

constexpr uint32_t POLL_INTERVAL_MS = 10;

void beginBle() {
  // アドバタイズはしないため、デバイス名は空にする
  NimBLEDevice::init("");
  // 受動スキャンにして、CoreS3自身は電波を出さずに機器のアドバタイズを聞くだけにする
  NimBLEDevice::getScan()->setActiveScan(false);
}

bool scanBle(RssiHistogram& histogram, uint32_t durationMs) {
  NimBLEScan* scan = NimBLEDevice::getScan();

  // 終わるまで待つgetResults(duration)は開始の失敗を返さないため、start()で開始して終了を待つ
  if (!scan->start(durationMs)) {
    return false;
  }
  while (scan->isScanning()) {
    delay(POLL_INTERVAL_MS);
  }

  NimBLEScanResults results = scan->getResults();
  for (int i = 0; i < results.getCount(); i++) {
    histogram.add(results.getDevice(i)->getRSSI());
  }
  return true;
}
