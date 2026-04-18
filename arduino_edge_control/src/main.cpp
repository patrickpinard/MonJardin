#include <Arduino.h>
#include <ArduinoJson.h>
#include <Arduino_EdgeControl.h>

#include "config.h"
#include "utils/Logger.h"
#include "utils/IrrigationGuard.h"
#include "sensors/SoilSensor.h"
#include "sensors/TempSensor.h"
#include "sensors/AnemometerSensor.h"
#include "actuators/ValveController.h"
#include "actuators/LinearActuator.h"
#include "communication/WiFiManager.h"
#include "communication/RestServer.h"
#include "ui/DisplayController.h"
#include "ui/ButtonController.h"

// ── Instances globales ────────────────────────────────────────────────────
SoilSensor        soilSensor;
TempSensor        tempSensor;
AnemometerSensor  anemometer;
ValveController   valves;
LinearActuator    roof;
WiFiManager       wifi;
RestServer        server;
IrrigationGuard   irrigGuard;
DisplayController display;
ButtonController  button;

// ── Cache capteurs ────────────────────────────────────────────────────────
SoilReading soilReadings[NUM_ZONES];
float       tempExt   = -127.0f;
float       tempSerre = -127.0f;

// ── Timers ────────────────────────────────────────────────────────────────
unsigned long lastSensorReadMs  = 0;
unsigned long lastTempRequestMs = 0;
unsigned long lastLogFlushMs    = 0;
unsigned long lastWindReadMs    = 0;
unsigned long lastDisplaySyncMs = 0;
unsigned long bootMs            = 0;

// ── Watchdog RPi ─────────────────────────────────────────────────────────
// Si le RPi ne contacte pas l'Arduino pendant RPI_WATCHDOG_MS,
// on passe en mode autonome (sécurité).
bool rpiWatchdogTriggered = false;

void checkRpiWatchdog() {
    unsigned long lastReq = server.lastRequestMs();
    if (lastReq == 0) return; // pas encore de requête depuis boot — attente normale
    if (millis() - lastReq > RPI_WATCHDOG_MS && !rpiWatchdogTriggered) {
        rpiWatchdogTriggered = true;
        Logger::log(LOG_WARNING, "WATCHDOG",
            "RPi injoignable depuis 5 min — mode autonome : fermeture préventive des vannes");
        valves.closeAll();
        roof.close();
        display.showAlert("! RPi injoignable", "Vannes fermees  ", 5000);
    }
    // Reset du flag si le RPi reprend contact
    if (rpiWatchdogTriggered && millis() - lastReq < RPI_WATCHDOG_MS) {
        rpiWatchdogTriggered = false;
        Logger::log(LOG_INFO, "WATCHDOG", "RPi de nouveau joignable — mode normal");
        display.showAlert("RPi reconnecte  ", "Mode normal     ", 3000);
    }
}

// ── Callbacks bouton ──────────────────────────────────────────────────────
void onButtonShortPress() {
    display.nextScreen();
}

void onButtonLongPress() {
    Logger::log(LOG_WARNING, "BUTTON", "Appui long — arrêt d'urgence : fermeture de toutes les vannes");
    valves.closeAll();
    display.showAlert("! ARRET URGENCE ", "Vannes fermees  ", 4000);
}

// ── Helpers affichage ─────────────────────────────────────────────────────
void syncDisplay() {
    DisplayData d;
    for (int i = 0; i < NUM_ZONES; i++) {
        d.moisture[i]  = soilReadings[i].valid ? soilReadings[i].moisturePct : -1.0f;
        d.valveOpen[i] = valves.isOpen(i + 1);
    }
    d.tempExt   = tempExt;
    d.tempSerre = tempSerre;
    d.windKmh   = anemometer.getKmh();
    d.wifiOk    = wifi.isConnected();
    d.rpiOk     = !rpiWatchdogTriggered;
    d.uptimeS   = (millis() - bootMs) / 1000UL;
    display.setData(d);
}

// ── Callbacks REST ────────────────────────────────────────────────────────
void onValveCommand(int zoneId, bool open) {
    if (rpiWatchdogTriggered) {
        Logger::log(LOG_WARNING, "REST", "Mode autonome actif — commande vanne ignorée");
        return;
    }
    if (open) {
        if (!irrigGuard.checkAndRecord(zoneId)) {
            Logger::logf(LOG_WARNING, "REST",
                "Zone %d : arrosage bloqué par IrrigationGuard", zoneId);
            return;
        }
    }
    valves.setValve(zoneId, open);
    syncDisplay();  // mise à jour immédiate affichage
}

void onRoofCommand(bool open) {
    if (rpiWatchdogTriggered) {
        Logger::log(LOG_WARNING, "REST", "Mode autonome actif — commande lucarne ignorée");
        return;
    }
    if (open) roof.open();
    else      roof.close();
}

void onGetSensors(String& out) {
    StaticJsonDocument<512> doc;
    doc["temperature_c"]   = isnan(tempExt)   ? JsonVariant() : JsonVariant(tempExt);
    doc["temp_serre_c"]    = isnan(tempSerre)  ? JsonVariant() : JsonVariant(tempSerre);
    doc["wind_speed_kmh"]  = anemometer.getKmh();

    JsonArray zones = doc.createNestedArray("zones");
    for (int i = 0; i < NUM_ZONES; i++) {
        JsonObject z = zones.createNestedObject();
        z["zone_id"]          = soilReadings[i].zoneId;
        z["soil_moisture_pct"]= soilReadings[i].valid ? JsonVariant(soilReadings[i].moisturePct) : JsonVariant();
        z["raw_adc"]          = soilReadings[i].rawAdc;
        z["valid"]            = soilReadings[i].valid;
    }
    serializeJson(doc, out);
}

void onGetActuators(String& out) {
    StaticJsonDocument<256> doc;
    doc["roof_state"] = roof.stateStr();
    JsonArray valvesArr = doc.createNestedArray("valves");
    for (int i = 1; i <= NUM_ZONES; i++) {
        JsonObject v = valvesArr.createNestedObject();
        v["zone_id"] = i;
        v["state"]   = valves.isOpen(i) ? "open" : "close";
    }
    serializeJson(doc, out);
}

// ── Setup ─────────────────────────────────────────────────────────────────
void setup() {
    bootMs = millis();
    Logger::begin(115200);
    Logger::log(LOG_INFO, "MAIN", "=== MonJardin Arduino Edge Control ===");
    Logger::logf(LOG_INFO, "MAIN", "Firmware v%s", FIRMWARE_VERSION);

    EdgeControl.begin();

    // SÉCURITÉ REBOOT : fermer toutes les vannes IMMÉDIATEMENT
    // avant toute autre initialisation
    valves.begin();   // begin() appelle closeAll() en interne
    Logger::log(LOG_INFO, "MAIN", "Sécurité reboot : toutes les vannes fermées");

    // Autres initialisations
    soilSensor.begin();
    tempSensor.begin();
    roof.begin();
    anemometer.begin();

    // Enclosure Kit — LCD + bouton
    display.begin();
    button.begin();
    button.onShortPress(onButtonShortPress);
    button.onLongPress(onButtonLongPress);
    Logger::log(LOG_INFO, "MAIN", "LCD 2x16 + bouton initialisés");

    // Première lecture capteurs
    tempSensor.requestTemperatures();
    delay(1000);
    tempExt   = tempSensor.getExterior();
    tempSerre = tempSensor.getGreenhouse();
    soilSensor.readAll(soilReadings);
    anemometer.read();
    syncDisplay();

    // WiFi
    wifi.begin();

    // Serveur REST
    server.onValve(onValveCommand);
    server.onRoof(onRoofCommand);
    server.onGetSensors(onGetSensors);
    server.onGetActuators(onGetActuators);
    server.begin(HTTP_PORT);

    Logger::log(LOG_INFO, "MAIN", "Initialisation terminée — attente des requêtes");
}

// ── Loop ──────────────────────────────────────────────────────────────────
void loop() {
    unsigned long now = millis();

    // 1. WiFi — reconnexion si nécessaire
    wifi.reconnectIfNeeded();

    // 2. Serveur HTTP — traitement des requêtes entrantes
    server.handleClients();

    // 3. Vérin lucarne — mise à jour état (fins de course, timeout)
    roof.update();

    // 4. Watchdog RPi — mode autonome si liaison perdue
    checkRpiWatchdog();

    // 5. Lecture capteurs sol (toutes les 30s)
    if (now - lastSensorReadMs >= 30000UL) {
        soilSensor.readAll(soilReadings);
        lastSensorReadMs = now;
    }

    // 6. Lecture température (requête asynchrone)
    if (now - lastTempRequestMs >= TEMP_READ_INTERVAL) {
        tempExt   = tempSensor.getExterior();
        tempSerre = tempSensor.getGreenhouse();
        tempSensor.requestTemperatures();
        lastTempRequestMs = now;
    }

    // 7. Vitesse du vent (lecture ADC toutes les 5s)
    if (now - lastWindReadMs >= 5000UL) {
        anemometer.read();
        lastWindReadMs = now;
    }

    // 8. Synchronisation données → affichage (toutes les 10s)
    if (now - lastDisplaySyncMs >= 10000UL) {
        syncDisplay();
        lastDisplaySyncMs = now;
    }

    // 9. LCD + bouton
    button.update();
    display.update();

    // 10. Envoi logs au RPi (toutes les 60s si WiFi dispo)
    if (now - lastLogFlushMs >= 60000UL) {
        if (wifi.isConnected()) {
            Logger::flushToRpi();
        }
        lastLogFlushMs = now;
    }

    delay(10);
}
