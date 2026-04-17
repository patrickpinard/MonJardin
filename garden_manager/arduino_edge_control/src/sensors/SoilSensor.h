#pragma once
#include <Arduino.h>
#include <Arduino_EdgeControl.h>

// Lecture capteur SoilWatch 10 via ADC du Edge Control
class SoilSensor {
public:
    // canal : constante INPUT_05V_CHxx de la bibliothèque EdgeControl
    explicit SoilSensor(int channel);
    void begin();

    // Retourne l'humidité en % (0–100), ou -1.0 si erreur
    float readMoisturePct();
    // Retourne la valeur ADC brute (0–4095)
    float readRawADC();

    // Coefficients de calibration (modifiables via EEPROM en v2)
    float vDry = 0.0f;   // Tension à sec (V)
    float vWet = 3.0f;   // Tension à saturation (V)
    float offsetPct = 0.0f;

private:
    int   _channel;
    float _adcToVolts(uint16_t raw) const;
    float _voltsToPct(float volts) const;
};
