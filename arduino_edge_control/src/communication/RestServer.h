#pragma once
#include <Arduino.h>
#include <WiFiNINA.h>
#include <ArduinoJson.h>
#include "../config.h"

// Callbacks depuis main.cpp
typedef void (*ValveCb)(int zoneId, bool open);
typedef void (*RoofCb)(bool open);
typedef void (*GetSensorsCb)(String& jsonOut);
typedef void (*GetActuatorsCb)(String& jsonOut);

class RestServer {
public:
    RestServer();
    void begin(int port = HTTP_PORT);

    void onValve(ValveCb cb)          { _valveCb = cb; }
    void onRoof(RoofCb cb)            { _roofCb  = cb; }
    void onGetSensors(GetSensorsCb cb)    { _sensorsCb = cb; }
    void onGetActuators(GetActuatorsCb cb){ _actuatorsCb = cb; }

    // À appeler dans loop() — non bloquant
    void handleClients();

    // Met à jour le timestamp de la dernière requête RPi reçue
    unsigned long lastRequestMs() const { return _lastRequestMs; }

private:
    WiFiServer   _server;
    ValveCb      _valveCb;
    RoofCb       _roofCb;
    GetSensorsCb     _sensorsCb;
    GetActuatorsCb   _actuatorsCb;
    unsigned long    _lastRequestMs;

    void _handleRequest(WiFiClient& client);
    void _send200(WiFiClient& client, const String& body);
    void _send400(WiFiClient& client, const char* msg);
    void _send404(WiFiClient& client);
    void _parseBody(WiFiClient& client, int contentLength, char* buf, int bufSize);
};
