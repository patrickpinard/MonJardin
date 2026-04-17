#include "TempSensor.h"

TempSensor::TempSensor(uint8_t pin) : _ow(pin), _dt(&_ow) {}

void TempSensor::begin() {
    _dt.begin();
    _dt.setResolution(12);  // Résolution maximale (12 bits = 0.0625°C)
    _initialized = _dt.getDeviceCount() > 0;
}

float TempSensor::readTemperatureC() {
    if (!_initialized) {
        // Tentative de relance
        _dt.begin();
        _initialized = _dt.getDeviceCount() > 0;
        if (!_initialized) return NAN;
    }
    _dt.requestTemperatures();
    float temp = _dt.getTempCByIndex(0);
    // La bibliothèque retourne DEVICE_DISCONNECTED_C (-127) si le capteur est absent
    if (temp == DEVICE_DISCONNECTED_C) {
        _initialized = false;
        return NAN;
    }
    return temp;
}

bool TempSensor::isConnected() {
    return _initialized && _dt.getDeviceCount() > 0;
}
