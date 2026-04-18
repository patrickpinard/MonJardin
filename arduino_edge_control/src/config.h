#pragma once

// ── WiFi ──────────────────────────────────────────────────────────────────
#define WIFI_SSID           "MonReseau"
#define WIFI_PASSWORD       "MotDePasse"
#define WIFI_RECONNECT_MS   30000UL   // tentative reconnexion toutes les 30s

// ── Raspberry Pi ──────────────────────────────────────────────────────────
#define RPI_HOST            "192.168.1.10"
#define RPI_PORT            5001
#define RPI_LOG_PATH        "/api/arduino/log"
#define RPI_ALERT_PATH      "/api/arduino/alert"
#define RPI_TIMEOUT_MS      5000

// ── Détection perte liaison RPi ───────────────────────────────────────────
// Si pas de requête du RPi depuis ce délai → mode autonome
#define RPI_WATCHDOG_MS     300000UL  // 5 minutes

// ── Sécurité arrosage fréquent ────────────────────────────────────────────
#define IRRIGATION_MAX_PER_HOUR     4   // déclenchements max par zone par heure
#define IRRIGATION_MIN_INTERVAL_MS  300000UL  // 5 min minimum entre deux arrosages
#define IRRIGATION_ALERT_COOLDOWN   3600000UL // 1h entre deux alertes email

// ── Capteurs sol (SoilWatch 10) ───────────────────────────────────────────
#define NUM_ZONES           4
#define ADC_DRY             3100    // valeur ADC à sec (à calibrer par zone)
#define ADC_WET             1200    // valeur ADC saturé (à calibrer par zone)
#define ADC_SAMPLES         8       // lectures moyennées

// ── Température DS18B20 ───────────────────────────────────────────────────
#define ONE_WIRE_BUS        5       // pin OneWire (D5 sur Edge Control)
#define TEMP_READ_INTERVAL  30000UL // lecture température toutes les 30s

// ── Anémomètre ────────────────────────────────────────────────────────────
#define ANEMOMETER_PIN      6       // pin impulsions (D6)
#define WIND_MEASURE_MS     3000UL  // fenêtre de mesure 3s
#define WIND_FACTOR         2.4f    // km/h par Hz (facteur calibration)

// ── Actionneurs ───────────────────────────────────────────────────────────
#define RELAY_PULSE_MS      50      // durée pulse relais latching (ms)
// Vérin lucarne
#define ACTUATOR_IN1        7       // pin direction H-bridge
#define ACTUATOR_IN2        8
#define ENDSTOP_OPEN        9       // fin de course ouvert
#define ENDSTOP_CLOSE       10      // fin de course fermé
#define ACTUATOR_TIMEOUT_MS 60000UL // timeout mouvement vérin

// ── Serveur HTTP embarqué ─────────────────────────────────────────────────
#define HTTP_PORT           80
#define HTTP_MAX_BODY       512

// ── Watchdog matériel ─────────────────────────────────────────────────────
#define WATCHDOG_TIMEOUT_MS 8000    // reset si pas de feed pendant 8s

// ── Firmware ──────────────────────────────────────────────────────────────
#define FIRMWARE_VERSION    "1.0.0"
