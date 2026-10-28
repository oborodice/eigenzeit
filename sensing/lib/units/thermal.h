#pragma once

constexpr int THERMAL_PIXEL_COUNT = 64;

bool beginThermal();
bool readThermal(float (&celsius)[THERMAL_PIXEL_COUNT]);
