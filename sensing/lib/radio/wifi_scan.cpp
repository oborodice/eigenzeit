#include "wifi_scan.h"

#include <WiFi.h>

#include "radio.h"

void setupWifi() {
  // スキャンにはステーションモードが必要。Arduino公式のスキャンの例に倣い、未接続の状態に揃える
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
}

void scanWifi() {
  // 受動スキャンにして、CoreS3自身は電波を出さずに基地局のビーコンを聞くだけにする
  // 名前を公開していない基地局も電波は出しているため、含める
  int count = WiFi.scanNetworks(/*async=*/false, /*show_hidden=*/true, /*passive=*/true);

  if (count < 0) {
    handleScanFailure("wifi_scan_failed");
    return;
  }

  RssiHistogram histogram;
  for (int i = 0; i < count; i++) {
    histogram.add(WiFi.RSSI(i));
  }
  WiFi.scanDelete();

  histogram.send("wifi_rssi_hist");
}
