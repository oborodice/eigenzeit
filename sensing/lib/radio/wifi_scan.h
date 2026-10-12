#pragma once

#include "rssi_histogram.h"

void beginWifi();
bool scanWifi(RssiHistogram& histogram);
