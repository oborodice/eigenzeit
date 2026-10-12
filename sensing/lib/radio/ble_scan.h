#pragma once

#include <stdint.h>

#include "rssi_histogram.h"

void beginBle();
bool scanBle(RssiHistogram& histogram, uint32_t durationMs);
