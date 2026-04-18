#pragma once
#include <Arduino.h>
#include <Arduino_EdgeControl.h>
#include "../config.h"

class ValveController {
public:
    ValveController();

    // Initialise les relais latching et ferme toutes les vannes (sécurité au boot)
    void begin();

    // Ouvre ou ferme une vanne (zone 1-4). Retourne false si zone invalide.
    bool setValve(int zoneId, bool open);

    // Ferme toutes les vannes immédiatement (failsafe)
    void closeAll();

    bool isOpen(int zoneId) const;

private:
    bool _states[NUM_ZONES];
    // channel = LATCHING_OUT_1..4, open=true → POSITIVE (relay fermé → 24V solénoïde)
    void _pulse(pin_size_t channel, bool open);
};
