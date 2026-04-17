#pragma once

// ====================================================================
// MonJardin — Configuration Arduino Edge Control
// ====================================================================

// --- WiFi ---
#define WIFI_SSID        "MonJardin"
#define WIFI_PASSWORD    "monjardin2024"
#define API_PORT         80

// --- Firmware ---
#ifndef FIRMWARE_VERSION
#define FIRMWARE_VERSION "1.0.0"
#endif

// --- Capteurs ---
#define NUM_ZONES        4
// Tension SoilWatch 10 à 100% d'humidité (V)
#define SOIL_V_MAX       3.0f
// Canal ADC du Edge Control pour chaque zone (InputExpander)
#define SOIL_ADC_Z1      INPUT_05V_CH01
#define SOIL_ADC_Z2      INPUT_05V_CH02
#define SOIL_ADC_Z3      INPUT_05V_CH03
#define SOIL_ADC_Z4      INPUT_05V_CH04
// DS18B20 : pin OneWire sur le connecteur personnalisé
#define DS18B20_PIN      CUST_4

// --- Relais latching (vannes 24V) ---
// Index relais sur le module EdgeControl (0-based)
#define RELAY_VALVE_Z1   0
#define RELAY_VALVE_Z2   1
#define RELAY_VALVE_Z3   2
#define RELAY_VALVE_Z4   3
// Durée impulsion pour relais latching (ms)
#define RELAY_PULSE_MS   50

// --- Vérin linéaire (toit serre) ---
#define ACTUATOR_IN1_PIN   CUST_1   // Sens ouverture
#define ACTUATOR_IN2_PIN   CUST_2   // Sens fermeture
#define ENDSTOP_OPEN_PIN   CUST_3   // Fin de course ouvert
#define ENDSTOP_CLOSE_PIN  CUST_5   // Fin de course fermé
// Timeout si fin de course jamais atteint (ms)
#define ACTUATOR_TIMEOUT_MS 60000UL

// --- Timings ---
// Intervalle de lecture capteurs (ms) — lecture à la demande REST uniquement
#define SENSOR_CACHE_TTL_MS  30000UL
// Watchdog timer (ms)
#define WATCHDOG_INTERVAL_MS 8000UL
// Délai reconnexion WiFi (ms)
#define WIFI_RECONNECT_DELAY_MS 5000UL
// Nombre max de tentatives WiFi au démarrage
#define WIFI_MAX_RETRIES 10
// Perte WiFi > ce délai → fermer toutes les vannes (ms)
#define WIFI_FAILSAFE_TIMEOUT_MS 300000UL  // 5 minutes
