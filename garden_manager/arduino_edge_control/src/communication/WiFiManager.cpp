#include "WiFiManager.h"
#include "../config.h"

bool WiFiManager::connect(const char* ssid, const char* password, uint8_t maxRetries) {
    _ssid = ssid;
    _password = password;
    Serial.print("Connexion WiFi à ");
    Serial.print(ssid);
    uint8_t attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < maxRetries) {
        WiFi.begin(ssid, password);
        delay(2000);
        Serial.print(".");
        attempts++;
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
        _everConnected = true;
        _lostMs = 0;
        Serial.print("IP : ");
        Serial.println(WiFi.localIP());
        return true;
    }
    Serial.println("Échec connexion WiFi");
    _lostMs = millis();
    return false;
}

bool WiFiManager::isConnected() {
    return WiFi.status() == WL_CONNECTED;
}

int8_t WiFiManager::getRSSI() {
    return WiFi.RSSI();
}

String WiFiManager::getLocalIP() {
    return WiFi.localIP().toString();
}

void WiFiManager::reconnectIfNeeded(const char* ssid, const char* password) {
    // Vérification toutes les 5 secondes
    if (millis() - _lastCheckMs < WIFI_RECONNECT_DELAY_MS) return;
    _lastCheckMs = millis();

    if (!isConnected()) {
        if (_lostMs == 0) _lostMs = millis();
        Serial.println("WiFi perdu — tentative reconnexion...");
        WiFi.begin(ssid, password);
    } else {
        _lostMs = 0;
    }
}

unsigned long WiFiManager::lostConnectionMs() const {
    if (isConnected() || _lostMs == 0) return 0;
    return millis() - _lostMs;
}
