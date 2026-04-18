#pragma once
#include <Arduino.h>
#include <Arduino_EdgeControl.h>
#include "../config.h"

struct SoilReading {
    int   zoneId;
    int   rawAdc;
    float moisturePct;
    bool  valid;
};

class SoilSensor {
public:
    SoilSensor();
    void begin();

    // Lit l'humidité d'une zone (1-4), moyenne sur ADC_SAMPLES lectures
    SoilReading read(int zoneId);

    // Lit toutes les zones
    void readAll(SoilReading results[NUM_ZONES]);

    // Calibration par zone (peut être surchargée depuis config)
    void setCalibration(int zoneId, int dry, int wet);

private:
    int _dry[NUM_ZONES];
    int _wet[NUM_ZONES];

    int _readAdc(int zoneId);
    float _toPercent(int raw, int dry, int wet);
};
