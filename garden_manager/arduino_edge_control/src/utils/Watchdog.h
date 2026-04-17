#pragma once
#include <Arduino.h>

// Watchdog matériel (reset si loop() ne répond plus)
class Watchdog {
public:
    void begin(uint32_t timeoutMs);
    void feed();  // À appeler régulièrement dans loop()
};
