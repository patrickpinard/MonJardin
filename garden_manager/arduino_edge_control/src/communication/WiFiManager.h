#pragma once
#include <Arduino.h>
#include <WiFiNINA.h>  // Module NINA-W102 du Edge Control

// Gestion connexion WiFi avec reconnexion automatique
class WiFiManager {
public:
    bool connect(const char* ssid, const char* password, uint8_t maxRetries = 10);
    bool isConnected();
    int8_t getRSSI();
    String getLocalIP();
    // À appeler dans loop() : reconnecte si nécessaire
    void reconnectIfNeeded(const char* ssid, const char* password);
    // Timestamp de la dernière perte de connexion (0 si connecté)
    unsigned long lostConnectionMs() const;

private:
    const char* _ssid     = nullptr;
    const char* _password = nullptr;
    unsigned long _lastCheckMs  = 0;
    unsigned long _lostMs       = 0;
    bool          _everConnected = false;
};
