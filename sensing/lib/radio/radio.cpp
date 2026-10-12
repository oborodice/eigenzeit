#include "radio.h"

#include <Arduino.h>
#include <esp_coexist.h>

#include "ble_scan.h"
#include "json_lines.h"
#include "rssi_histogram.h"
#include "wifi_scan.h"

// アドバタイズの間隔が長い機器も取りこぼさないよう、数秒聞く
constexpr uint32_t BLE_SCAN_DURATION_MS = 4000;

constexpr uint32_t SCAN_RETRY_DELAY_MS = 1000;

// 失敗が続いたときに空回りしないよう、待ってから次のスキャンに進む
static void handleScanFailure(const char* error) {
  sendError(error);
  delay(SCAN_RETRY_DELAY_MS);
}

static void scanAndSendWifi() {
  RssiHistogram histogram;
  if (!scanWifi(histogram)) {
    handleScanFailure("wifi_scan_failed");
    return;
  }
  histogram.send("wifi_rssi_hist");
}

static void scanAndSendBle() {
  RssiHistogram histogram;
  if (!scanBle(histogram, BLE_SCAN_DURATION_MS)) {
    handleScanFailure("ble_scan_failed");
    return;
  }
  histogram.send("ble_rssi_hist");
}

void beginRadio() {
  beginWifi();
  beginBle();
}

void scanRadio() {
  // Wi-FiとBLEは同じアンテナを使うため、交互にスキャンする
  // 優先を切り替えないと、Wi-Fiのスキャン中もBLEにアンテナを取られ、近くの基地局を取りこぼす
  // esp_coex_preference_setは新しい版のSDKでは非推奨のため、プラットフォームを更新する際は置き換えが必要
  esp_coex_preference_set(ESP_COEX_PREFER_WIFI);
  scanAndSendWifi();
  esp_coex_preference_set(ESP_COEX_PREFER_BT);
  scanAndSendBle();
}
