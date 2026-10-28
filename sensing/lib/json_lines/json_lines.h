#pragma once

void sendInt(const char* key, int value);
void sendIntArray(const char* key, const int* values, int count);
void sendFloatArray(const char* key, const float* values, int count, int decimals);
void sendError(const char* error);
