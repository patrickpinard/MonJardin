#include "SoilSensor.h"
#include "../utils/Logger.h"
#include <Arduino_EdgeControl.h>

// Mapping zone_id → canal Input 0-5V (INPUT_05V_CH01=0 … INPUT_05V_CH04=3)
static const pin_size_t SOIL_CH[NUM_ZONES] = {
    INPUT_05V_CH01,
    INPUT_05V_CH02,
    INPUT_05V_CH03,
    INPUT_05V_CH04,
};

SoilSensor::SoilSensor() {
    for (int i = 0; i < NUM_ZONES; i++) {
        _dry[i] = ADC_DRY;
        _wet[i] = ADC_WET;
    }
}

void SoilSensor::begin() {
    Input.begin();
    Input.enable();  // active l'alimentation du circuit 0-5V
    Logger::log(LOG_INFO, "SOIL", "Capteurs sol initialisés (Input 0-5V)");
}

void SoilSensor::setCalibration(int zoneId, int dry, int wet) {
    if (zoneId < 1 || zoneId > NUM_ZONES) return;
    _dry[zoneId - 1] = dry;
    _wet[zoneId - 1] = wet;
}

SoilReading SoilSensor::read(int zoneId) {
    SoilReading r;
    r.zoneId = zoneId;
    r.valid  = false;

    if (zoneId < 1 || zoneId > NUM_ZONES) {
        Logger::logf(LOG_ERROR, "SOIL", "Zone invalide : %d", zoneId);
        return r;
    }

    r.rawAdc      = _readAdc(zoneId);
    r.moisturePct = _toPercent(r.rawAdc, _dry[zoneId-1], _wet[zoneId-1]);
    r.valid       = true;

    Logger::logf(LOG_DEBUG, "SOIL", "Zone %d ADC=%d -> %.1f%%",
                 zoneId, r.rawAdc, r.moisturePct);
    return r;
}

void SoilSensor::readAll(SoilReading results[NUM_ZONES]) {
    for (int i = 0; i < NUM_ZONES; i++) {
        results[i] = read(i + 1);
    }
}

int SoilSensor::_readAdc(int zoneId) {
    pin_size_t ch = SOIL_CH[zoneId - 1];
    long sum = 0;
    for (int s = 0; s < ADC_SAMPLES; s++) {
        sum += Input.analogRead(ch);
        delay(5);
    }
    return (int)(sum / ADC_SAMPLES);
}

float SoilSensor::_toPercent(int raw, int dry, int wet) {
    if (dry == wet) return 50.0f;
    float pct = 100.0f * (dry - raw) / (float)(dry - wet);
    return constrain(pct, 0.0f, 100.0f);
}
