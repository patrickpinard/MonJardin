/*
 * MonJardin — Firmware Arduino Edge Control
 * Acquisition 4 zones (SoilWatch10 + DS18B20) + pilotage vannes + vérin toit
 * Serveur HTTP REST embarqué sur port 80
 */
#include <Arduino.h>
#include <Arduino_EdgeControl.h>
#include "config.h"
#include "sensors/SoilSensor.h"
#include "sensors/TempSensor.h"
#include "actuators/ValveController.h"
#include "actuators/LinearActuator.h"
#include "communication/WiFiManager.h"
#include "communication/RestServer.h"
#include "utils/Watchdog.h"
#include "utils/Logger.h"

// ---- Instances globales ----
SoilSensor soilSensors[NUM_ZONES] = {
    SoilSensor(SOIL_ADC_Z1),
    SoilSensor(SOIL_ADC_Z2),
    SoilSensor(SOIL_ADC_Z3),
    SoilSensor(SOIL_ADC_Z4),
};
TempSensor    tempSensor(DS18B20_PIN);
ValveController valves[NUM_ZONES] = {
    ValveController(RELAY_VALVE_Z1),
    ValveController(RELAY_VALVE_Z2),
    ValveController(RELAY_VALVE_Z3),
    ValveController(RELAY_VALVE_Z4),
};
LinearActuator roofActuator(ACTUATOR_IN1_PIN, ACTUATOR_IN2_PIN,
                             ENDSTOP_OPEN_PIN, ENDSTOP_CLOSE_PIN);
WiFiManager   wifiMgr;
RestServer    server(API_PORT);
Watchdog      watchdog;

// Cache des dernières mesures capteurs
SensorSnapshot  sensorCache   = {};
ActuatorSnapshot actuatorCache = {};
unsigned long   lastSensorReadMs = 0;

// ---- Mise à jour du cache capteurs ----
void readSensors() {
    sensorCache.temperature = tempSensor.readTemperatureC();
    if (isnan(sensorCache.temperature)) sensorCache.temperature = -99.0f;

    for (int i = 0; i < NUM_ZONES; i++) {
        sensorCache.moisture[i] = soilSensors[i].readMoisturePct();
        sensorCache.rawAdc[i]   = soilSensors[i].readRawADC();
    }
    sensorCache.tsMs = millis();
}

// ---- Synchronisation état actionneurs → cache ----
void syncActuatorCache() {
    for (int i = 0; i < NUM_ZONES; i++) {
        bool desired = actuatorCache.valveOpen[i];
        if (desired && !valves[i].isOpen()) valves[i].open();
        if (!desired && valves[i].isOpen()) valves[i].close();
    }
    // Le toit est géré séparément via l'état "moving"
    const char* roofState = actuatorCache.roofState;
    if (roofState) {
        if (strcmp(roofState, "open") == 0 && !roofActuator.isMoving()) {
            roofActuator.open();
        } else if (strcmp(roofState, "close") == 0 && !roofActuator.isMoving()) {
            roofActuator.close();
        }
    }
    // Mise à jour de l'état réel du toit dans le cache
    actuatorCache.roofState = roofActuator.getState();
}

// ---- Failsafe : perte WiFi prolongée ----
void checkWifiFailsafe() {
    unsigned long lost = wifiMgr.lostConnectionMs();
    if (lost > WIFI_FAILSAFE_TIMEOUT_MS) {
        LOGF("FAILSAFE : WiFi perdu depuis %lums — fermeture vannes et toit", lost);
        for (int i = 0; i < NUM_ZONES; i++) {
            valves[i].close();
            actuatorCache.valveOpen[i] = false;
        }
        roofActuator.close();
        actuatorCache.roofState = "close";
    }
}

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("=== MonJardin Firmware v" FIRMWARE_VERSION " ===");

    // Initialisation du module Edge Control
    EdgeControl.begin();

    // Initialisation capteurs
    tempSensor.begin();
    for (int i = 0; i < NUM_ZONES; i++) soilSensors[i].begin();

    // Initialisation actionneurs (fermeture par sécurité)
    for (int i = 0; i < NUM_ZONES; i++) valves[i].begin();
    roofActuator.begin();
    actuatorCache.roofState = roofActuator.getState();

    // Initialisation cache actionneurs
    for (int i = 0; i < NUM_ZONES; i++) actuatorCache.valveOpen[i] = false;

    // Connexion WiFi
    bool connected = wifiMgr.connect(WIFI_SSID, WIFI_PASSWORD, WIFI_MAX_RETRIES);
    if (connected) {
        server.begin();
    } else {
        LOG("WiFi non disponible au démarrage — tentatives en cours...");
    }

    // Première lecture capteurs
    readSensors();

    // Watchdog en dernier
    watchdog.begin(WATCHDOG_INTERVAL_MS);
    LOG("Setup terminé.");
}

void loop() {
    // 1. Reconnexion WiFi si nécessaire
    wifiMgr.reconnectIfNeeded(WIFI_SSID, WIFI_PASSWORD);
    if (!wifiMgr.isConnected()) {
        checkWifiFailsafe();
        watchdog.feed();
        delay(100);
        return;
    }

    // 2. Rafraîchissement cache capteurs (toutes les 30s)
    if (millis() - lastSensorReadMs >= SENSOR_CACHE_TTL_MS || lastSensorReadMs == 0) {
        readSensors();
        lastSensorReadMs = millis();
    }

    // 3. Traitement des requêtes REST (non-bloquant)
    server.handleClients(sensorCache, actuatorCache);

    // 4. Synchronisation actionneurs si le cache a été modifié par le serveur REST
    syncActuatorCache();

    // 5. Mise à jour fin de course vérin
    roofActuator.update();

    // 6. Watchdog — preuve que la loop tourne
    watchdog.feed();

    delay(10);
}
