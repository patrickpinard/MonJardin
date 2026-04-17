#pragma once
#include <Arduino.h>
#include <WiFiNINA.h>
#include <ArduinoJson.h>

// Référence aux données globales (définies dans main.cpp)
struct SensorSnapshot {
    float moisture[4];   // Humidité zones 1-4 (%)
    float rawAdc[4];     // ADC brut zones 1-4
    float temperature;   // °C
    unsigned long tsMs;  // Timestamp millis() de la dernière lecture
};

struct ActuatorSnapshot {
    bool valveOpen[4];   // État vannes zones 1-4
    const char* roofState;  // "open", "close", "moving", "unknown"
};

// Serveur HTTP REST embarqué (parsing manuel, pas de framework)
class RestServer {
public:
    explicit RestServer(uint16_t port = 80);
    void begin();
    // Non-bloquant — à appeler dans loop()
    void handleClients(const SensorSnapshot& sensors, ActuatorSnapshot& actuators);

private:
    WiFiServer _server;
    unsigned long _startMs;

    void _handleRequest(WiFiClient& client, const SensorSnapshot& sensors,
                        ActuatorSnapshot& actuators);
    void _sendJson(WiFiClient& client, int status, const String& body);
    void _sendError(WiFiClient& client, int status, const char* msg);

    // Handlers par route
    void _handleSensors(WiFiClient& client, const SensorSnapshot& s, int zoneFilter);
    void _handleActuatorStatus(WiFiClient& client, const ActuatorSnapshot& a);
    void _handleSetValve(WiFiClient& client, ActuatorSnapshot& a, int zoneId, const String& body);
    void _handleSetRoof(WiFiClient& client, ActuatorSnapshot& a, const String& body);
    void _handleHealth(WiFiClient& client);
};
