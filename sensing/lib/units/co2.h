#pragma once

#include <stdint.h>

enum class Co2Reading { Failed, NotReady, Ready };

bool beginCo2();
// 新しい値が出ていれば、Readyを返してppmに入れる
Co2Reading readCo2(uint16_t& ppm);
