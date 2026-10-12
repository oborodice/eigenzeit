#include "ble_scan.h"

#include <Arduino.h>
#include <NimBLEDevice.h>

#include "radio.h"

// Wi-FiとBLEで、1回に電波を聞く時間を揃える
constexpr uint32_t BLE_SCAN_DURATION_MS = 4000;
constexpr uint32_t BLE_SCAN_POLL_INTERVAL_MS = 10;

void setupBle() {
  // アドバタイズはしないため、デバイス名は空にする
  NimBLEDevice::init("");
  NimBLEScan* scan = NimBLEDevice::getScan();
  // 受動スキャンにして、CoreS3自身は電波を出さずに機器のアドバタイズを聞くだけにする
  scan->setActiveScan(false);
}

void scanBle() {
  NimBLEScan* scan = NimBLEDevice::getScan();

  // 終わるまで待つgetResults(duration)は開始の失敗を返さないため、start()で開始して終了を待つ
  if (!scan->start(BLE_SCAN_DURATION_MS)) {
    handleScanFailure("ble_scan_failed");
    return;
  }
  while (scan->isScanning()) {
    delay(BLE_SCAN_POLL_INTERVAL_MS);
  }

  NimBLEScanResults results = scan->getResults();
  RssiHistogram histogram;
  for (int i = 0; i < results.getCount(); i++) {
    histogram.add(results.getDevice(i)->getRSSI());
  }
  scan->clearResults();

  histogram.send("ble_rssi_hist");
}
