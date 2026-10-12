#include <M5CoreS3.h>
#include <WiFi.h>

constexpr uint32_t SERIAL_BAUD_RATE = 115200;

constexpr int RSSI_MIN_DBM = -100;
constexpr int RSSI_STEP_DB = 10;
constexpr int RSSI_BIN_COUNT = 8;

constexpr uint32_t SCAN_RETRY_DELAY_MS = 1000;

int rssiToBin(int rssi) {
  // 区間は下端を含み上端を含まない
  int bin = (rssi - RSSI_MIN_DBM) / RSSI_STEP_DB;
  // 範囲外の値は両端の区間に含める
  return constrain(bin, 0, RSSI_BIN_COUNT - 1);
}

void sendHistogram(const char* key, const int* histogram) {
  Serial.printf("{\"time_ms\": %lu, \"%s\": [", millis(), key);
  for (int i = 0; i < RSSI_BIN_COUNT; i++) {
    if (i > 0) Serial.print(", ");
    Serial.print(histogram[i]);
  }
  Serial.println("]}");
}

void sendError(const char* error) {
  Serial.printf("{\"time_ms\": %lu, \"error\": \"%s\"}\n", millis(), error);
}

void scanWifi() {
  // 受動スキャンにして、CoreS3自身は電波を出さずに基地局のビーコンを聞くだけにする
  int count = WiFi.scanNetworks(/*async=*/false, /*show_hidden=*/true, /*passive=*/true);

  // 失敗時は負の値が返る。失敗が続いたときに空回りしないよう、待ってから次のスキャンに進む
  if (count < 0) {
    sendError("wifi_scan_failed");
    delay(SCAN_RETRY_DELAY_MS);
    return;
  }

  int histogram[RSSI_BIN_COUNT] = {0};
  for (int i = 0; i < count; i++) {
    histogram[rssiToBin(WiFi.RSSI(i))]++;
  }
  WiFi.scanDelete();

  sendHistogram("wifi_rssi_hist", histogram);
}

void setup() {
  auto cfg = M5.config();
  CoreS3.begin(cfg);

  // CoreS3.begin()は初期設定ではシリアルを開始しないため、ここで開始する
  Serial.begin(SERIAL_BAUD_RATE);

  // スキャンにはステーションモードが必要。Arduino公式のスキャンの例に倣い、未接続の状態に揃える
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
}

void loop() {
  // 受動スキャン1回に約4秒かかるため、待ち時間は入れない
  scanWifi();
}
