#include "SoilSensor.h"
#include "../config.h"

SoilSensor::SoilSensor(int channel) : _channel(channel) {}

void SoilSensor::begin() {
    // Le EdgeControl.begin() est appelé dans main — rien de spécifique ici
}

float SoilSensor::readRawADC() {
    // Lecture via l'expanseur d'entrée du Edge Control
    float volts = EdgeControl.getVoltage(_channel);
    // Conversion en ADC 12 bits équivalent (0–4095 pour 0–3V)
    return (volts / 3.3f) * 4095.0f;
}

float SoilSensor::readMoisturePct() {
    float raw = readRawADC();
    float volts = _adcToVolts((uint16_t)raw);
    return _voltsToPct(volts);
}

float SoilSensor::_adcToVolts(uint16_t raw) const {
    return (float)raw / 4095.0f * 3.3f;
}

float SoilSensor::_voltsToPct(float volts) const {
    if (vWet <= vDry) return 0.0f;  // Calibration invalide
    float pct = (volts - vDry) / (vWet - vDry) * 100.0f + offsetPct;
    // Clamp 0–100%
    if (pct < 0.0f) pct = 0.0f;
    if (pct > 100.0f) pct = 100.0f;
    return pct;
}
