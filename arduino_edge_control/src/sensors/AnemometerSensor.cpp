#include "AnemometerSensor.h"
#include <Arduino_EdgeControl.h>
#include "../utils/Logger.h"

void AnemometerSensor::begin() {
    // L'InputExpander est initialisé par EdgeControl.begin() dans main.cpp
    Logger::logf(LOG_INFO, "ANEMOMETER",
        "QS-FS01 initialisé sur canal ADC %d", ANEMOMETER_ADC_CH);
}

float AnemometerSensor::read() {
    long sum = 0;
    for (int i = 0; i < WIND_ADC_SAMPLES; i++) {
        sum += InputExpander.analogRead(ANEMOMETER_ADC_CH);
        delayMicroseconds(500);
    }
    int avgAdc = (int)(sum / WIND_ADC_SAMPLES);

    float voltage = _adcToVoltage(avgAdc);
    float ms      = _voltageToMs(voltage);
    _windKmh      = ms * 3.6f;

    return _windKmh;
}
