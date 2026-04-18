#include "ValveController.h"
#include "../utils/Logger.h"
#include <Arduino_EdgeControl.h>

// Mapping zone_id → canal Latching (LATCHING_OUT_1=0 … LATCHING_OUT_4=3)
static const pin_size_t LATCH_CH[NUM_ZONES] = {
    LATCHING_OUT_1,
    LATCHING_OUT_2,
    LATCHING_OUT_3,
    LATCHING_OUT_4,
};

ValveController::ValveController() {
    for (int i = 0; i < NUM_ZONES; i++) _states[i] = false;
}

void ValveController::begin() {
    Latching.begin();
    // Sécurité boot : fermer toutes les vannes immédiatement
    closeAll();
    Logger::log(LOG_INFO, "VALVE", "Initialisation : toutes les vannes fermees");
}

bool ValveController::setValve(int zoneId, bool open) {
    if (zoneId < 1 || zoneId > NUM_ZONES) {
        Logger::logf(LOG_ERROR, "VALVE", "Zone invalide : %d", zoneId);
        return false;
    }
    int idx = zoneId - 1;
    if (_states[idx] == open) return true;

    _pulse(LATCH_CH[idx], open);
    _states[idx] = open;
    Logger::logf(LOG_INFO, "VALVE", "Zone %d vanne %s", zoneId, open ? "OUVERTE" : "FERMEE");
    return true;
}

void ValveController::closeAll() {
    for (int i = 0; i < NUM_ZONES; i++) {
        _pulse(LATCH_CH[i], false);
        _states[i] = false;
    }
    Logger::log(LOG_INFO, "VALVE", "Toutes les vannes fermees");
}

bool ValveController::isOpen(int zoneId) const {
    if (zoneId < 1 || zoneId > NUM_ZONES) return false;
    return _states[zoneId - 1];
}

void ValveController::_pulse(pin_size_t channel, bool open) {
    // Vanne GARDENA 24V (solénoïde NC) — besoin de 24V continu pour rester ouverte.
    // Le relais latching de l'Edge Control maintient ses contacts sans alimentation.
    //
    // POSITIVE → contacts fermés → 24V permanent sur bobine → vanne ouverte
    // NEGATIVE → contacts ouverts → hors tension → ressort ferme la vanne
    PulseDirection dir = open ? POSITIVE : NEGATIVE;
    Latching.channelDirection(channel, dir);
    Latching.strobe(RELAY_PULSE_MS);
}
