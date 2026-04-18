#include "AnemometerSensor.h"
#include <Arduino_EdgeControl.h>
#include "../utils/Logger.h"

void AnemometerSensor::begin() {
    // Input.begin()/enable() est appelé par SoilSensor.begin() — pas de double init
    Logger::logf(LOG_INFO, "ANEMOMETER",
        "QS-FS01 initialisé sur canal Input 0-5V #%d", ANEMOMETER_ADC_CH);
}

float AnemometerSensor::read() {
    long sum = 0;
    for (int i = 0; i < WIND_ADC_SAMPLES; i++) {
        sum += Input.analogRead(ANEMOMETER_ADC_CH);  // INPUT_05V_CH05 = 4
        delayMicroseconds(500);
    }
    int avgAdc = (int)(sum / WIND_ADC_SAMPLES);

    float voltage = _adcToVoltage(avgAdc);
    float ms      = _voltageToMs(voltage);
    _windKmh      = ms * 3.6f;

    return _windKmh;
}
