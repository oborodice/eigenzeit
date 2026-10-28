#pragma once

// PaHubの先に繋いだ赤外線とCO2のユニット
void beginUnits();
// 1回分を読んで送り、次に読む時刻まで待つ
void readUnits();
