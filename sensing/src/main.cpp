#include <M5CoreS3.h>

void setup() {
  auto cfg = M5.config();
  CoreS3.begin(cfg);

  Serial.begin(115200);
}

void loop() {
  Serial.println("hello, world!");
  delay(1000);
}
