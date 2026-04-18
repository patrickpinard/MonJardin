#pragma once
#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "../config.h"

class TempSensor {
public:
    TempSensor();
    void begin();

    // Déclenche une lecture (non bloquante si async = true)
    void requestTemperatures();

    float getExterior();   // DS18B20 adresse 0
    float getGreenhouse(); // DS18B20 adresse 1

    bool isValid(float t) const { return t > -55.0f && t < 85.0f; }

private:
    OneWire          _oneWire;
    DallasTemperature _sensors;
    float _tempExt;
    float _tempSerre;
};
