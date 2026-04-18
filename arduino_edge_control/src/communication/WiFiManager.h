#pragma once
#include <Arduino.h>
#include <WiFiNINA.h>
#include "../config.h"

class WiFiManager {
public:
    WiFiManager();
    void begin();

    // À appeler dans loop() — reconnecte si nécessaire
    bool reconnectIfNeeded();

    bool isConnected() const;
    String localIP() const;
    int rssi() const;

private:
    unsigned long _lastAttemptMs;
    int           _failCount;
    bool          _connect();
};
