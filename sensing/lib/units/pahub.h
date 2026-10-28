#pragma once

#include <stdint.h>

// PaHubの先に繋いだユニットと通信する前に、そのユニットのチャンネルを選ぶ
bool selectPaHubChannel(uint8_t channel);
