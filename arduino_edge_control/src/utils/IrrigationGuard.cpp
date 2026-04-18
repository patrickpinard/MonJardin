#include "IrrigationGuard.h"
#include "Logger.h"
#include "../config.h"
#include <WiFiNINA.h>
#include <ArduinoJson.h>

IrrigationGuard::IrrigationGuard() {
    for (int i = 0; i < MAX_ZONES; i++) {
        _stats[i] = {0, 0, 0, 0};
    }
}

bool IrrigationGuard::checkAndRecord(int zoneId) {
    if (zoneId < 1 || zoneId > MAX_ZONES) return false;
    ZoneStats& s = _stats[zoneId - 1];
    unsigned long now = millis();

    // Fenêtre glissante d'une heure
    if (now - s.hourWindowStartMs > 3600000UL) {
        s.countLastHour = 0;
        s.hourWindowStartMs = now;
    }

    // Intervalle minimum entre deux arrosages
    if (s.lastOpenMs > 0 && (now - s.lastOpenMs) < IRRIGATION_MIN_INTERVAL_MS) {
        Logger::logf(LOG_WARNING, "GUARD",
            "Zone %d : arrosage trop recent (%lus ago)",
            zoneId, (now - s.lastOpenMs) / 1000);
        s.countLastHour++;
        if (s.countLastHour >= IRRIGATION_MAX_PER_HOUR) {
            sendAlert(zoneId);
        }
        return false;
    }

    s.countLastHour++;
    s.lastOpenMs = now;

    if (s.countLastHour >= IRRIGATION_MAX_PER_HOUR) {
        sendAlert(zoneId);
        return false;
    }

    return true;
}

void IrrigationGuard::sendAlert(int zoneId) {
    ZoneStats& s = _stats[zoneId - 1];
    unsigned long now = millis();

    // Anti-spam : une alerte max par heure par zone
    if (s.lastAlertMs > 0 && (now - s.lastAlertMs) < IRRIGATION_ALERT_COOLDOWN) return;
    s.lastAlertMs = now;

    Logger::logf(LOG_ERROR, "GUARD",
        "ALERTE zone %d : %d arrosages en 1h — envoi alerte",
        zoneId, s.countLastHour);

    if (WiFi.status() != WL_CONNECTED) {
        Logger::log(LOG_WARNING, "GUARD", "WiFi indisponible — alerte non envoyée");
        return;
    }

    WiFiClient client;
    if (!client.connect(RPI_HOST, RPI_PORT)) {
        Logger::log(LOG_WARNING, "GUARD", "RPi injoignable — alerte non envoyée");
        return;
    }

    StaticJsonDocument<256> doc;
    doc["zone_id"]  = zoneId;
    doc["count"]    = s.countLastHour;
    doc["type"]     = "irrigation_overflow";
    doc["message"]  = String("Zone ") + zoneId + " : arrosage trop frequent (" + s.countLastHour + " fois en 1h)";
    String body;
    serializeJson(doc, body);

    client.println("POST " RPI_ALERT_PATH " HTTP/1.1");
    client.print("Host: "); client.println(RPI_HOST);
    client.println("Content-Type: application/json");
    client.print("Content-Length: "); client.println(body.length());
    client.println("Connection: close");
    client.println();
    client.print(body);

    unsigned long t = millis();
    while (client.available() == 0 && millis() - t < 2000);
    client.stop();
}

void IrrigationGuard::resetZone(int zoneId) {
    if (zoneId < 1 || zoneId > MAX_ZONES) return;
    _stats[zoneId - 1] = {0, 0, 0, 0};
}
