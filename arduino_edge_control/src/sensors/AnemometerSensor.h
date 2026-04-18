#pragma once
#include <Arduino.h>
#include "../config.h"

class AnemometerSensor {
public:
    AnemometerSensor() : _windKmh(0.0f) {}

    void begin();

    // Lit la vitesse instantanée (moyenne de WIND_ADC_SAMPLES lectures ADC)
    // Retourne la vitesse en km/h. Met à jour le cache interne.
    float read();

    float getKmh() const { return _windKmh; }

private:
    float _windKmh;

    // ADC 16-bit → tension (V), référence 3.3V sur InputExpander
    static float _adcToVoltage(int raw) {
        return raw * (3.3f / 65535.0f);
    }

    // Formule datasheet QS-FS01 : (V - V_zero) / (V_full - V_zero) * V_max_ms
    static float _voltageToMs(float v) {
        if (v <= WIND_V_ZERO) return 0.0f;
        float span = WIND_V_FULL - WIND_V_ZERO;
        return ((v - WIND_V_ZERO) / span) * WIND_MS_MAX;
    }
};
