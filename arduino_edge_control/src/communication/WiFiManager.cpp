#include "WiFiManager.h"
#include "../utils/Logger.h"

WiFiManager::WiFiManager() : _lastAttemptMs(0), _failCount(0) {}

void WiFiManager::begin() {
    Logger::logf(LOG_INFO, "WIFI", "Connexion à %s ...", WIFI_SSID);
    if (!_connect()) {
        Logger::log(LOG_WARNING, "WIFI", "Connexion initiale échouée — retry en background");
    }
}

bool WiFiManager::reconnectIfNeeded() {
    if (WiFi.status() == WL_CONNECTED) {
        _failCount = 0;
        return true;
    }
    unsigned long now = millis();
    if (now - _lastAttemptMs < WIFI_RECONNECT_MS) return false;
    _lastAttemptMs = now;

    Logger::logf(LOG_WARNING, "WIFI", "Reconnexion... (tentative %d)", ++_failCount);
    return _connect();
}

bool WiFiManager::isConnected() const {
    return WiFi.status() == WL_CONNECTED;
}

String WiFiManager::localIP() const {
    return WiFi.localIP().toString();
}

int WiFiManager::rssi() const {
    return WiFi.RSSI();
}

bool WiFiManager::_connect() {
    int status = WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    unsigned long t = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t < 10000) delay(500);

    if (WiFi.status() == WL_CONNECTED) {
        Logger::logf(LOG_INFO, "WIFI", "Connecté — IP %s RSSI %d dBm",
                     WiFi.localIP().toString().c_str(), WiFi.RSSI());
        _failCount = 0;
        return true;
    }
    Logger::log(LOG_ERROR, "WIFI", "Échec connexion WiFi");
    return false;
}
