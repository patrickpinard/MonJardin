#pragma once
#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// Lecture DS18B20 via protocole OneWire
class TempSensor {
public:
    explicit TempSensor(uint8_t pin);
    void begin();
    // Retourne la température en °C, ou NAN si erreur/déconnecté
    float readTemperatureC();
    bool isConnected();

private:
    OneWire          _ow;
    DallasTemperature _dt;
    bool _initialized = false;
};
