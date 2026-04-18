#include "TempSensor.h"
#include "../utils/Logger.h"

TempSensor::TempSensor()
    : _oneWire(ONE_WIRE_BUS),
      _sensors(&_oneWire),
      _tempExt(-127.0f),
      _tempSerre(-127.0f) {}

void TempSensor::begin() {
    _sensors.begin();
    int found = _sensors.getDeviceCount();
    Logger::logf(LOG_INFO, "TEMP", "%d capteur(s) DS18B20 détecté(s)", found);
    if (found == 0) {
        Logger::log(LOG_WARNING, "TEMP", "Aucun DS18B20 détecté — vérifier câblage OneWire");
    }
    _sensors.setWaitForConversion(false); // mode asynchrone
}

void TempSensor::requestTemperatures() {
    _sensors.requestTemperatures();
}

float TempSensor::getExterior() {
    float t = _sensors.getTempCByIndex(0);
    if (!isValid(t)) {
        Logger::logf(LOG_WARNING, "TEMP", "Température extérieure invalide : %.1f°C", t);
        return _tempExt; // retourne dernière valeur connue
    }
    _tempExt = t;
    return t;
}

float TempSensor::getGreenhouse() {
    float t = _sensors.getTempCByIndex(1);
    if (!isValid(t)) {
        Logger::logf(LOG_WARNING, "TEMP", "Température serre invalide : %.1f°C", t);
        return _tempSerre;
    }
    _tempSerre = t;
    return t;
}
