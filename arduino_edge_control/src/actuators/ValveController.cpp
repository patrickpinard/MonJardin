#include "ValveController.h"
#include "../utils/Logger.h"

// Mapping zone_id → index relais Edge Control (0-based)
static const int RELAY_INDEX[NUM_ZONES] = {0, 1, 2, 3};

ValveController::ValveController() {
    for (int i = 0; i < NUM_ZONES; i++) _states[i] = false;
}

void ValveController::begin() {
    Relay.begin();
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
    if (_states[idx] == open) return true;  // déjà dans l'état désiré

    _pulse(RELAY_INDEX[idx], open);
    _states[idx] = open;
    Logger::logf(LOG_INFO, "VALVE", "Zone %d vanne %s", zoneId, open ? "OUVERTE" : "FERMEE");
    return true;
}

void ValveController::closeAll() {
    for (int i = 0; i < NUM_ZONES; i++) {
        if (_states[i]) {
            _pulse(RELAY_INDEX[i], false);
            _states[i] = false;
        } else {
            // Forcer la fermeture même si on pense qu'elle est déjà fermée (sécurité reboot)
            _pulse(RELAY_INDEX[i], false);
        }
    }
    Logger::log(LOG_INFO, "VALVE", "Toutes les vannes fermees");
}

bool ValveController::isOpen(int zoneId) const {
    if (zoneId < 1 || zoneId > NUM_ZONES) return false;
    return _states[zoneId - 1];
}

void ValveController::_pulse(int relayIndex, bool open) {
    // Vanne GARDENA 24V (solénoïde, normalement fermée) :
    //   - besoin de 24V CONTINU pour rester ouverte
    //   - se referme par ressort dès que la tension est coupée
    //
    // Le relais latching Edge Control fournit ce 24V continu :
    //   open  → impulsion SET   (Relay.on)  → relais latchisé fermé  → 24V permanent sur bobine
    //   close → impulsion RESET (Relay.off) → relais latchisé ouvert → bobine hors tension → ressort
    if (open) {
        Relay.on(relayIndex);
        delay(RELAY_PULSE_MS);
        // relais reste latchisé FERMÉ — pas de Relay.off() ici
    } else {
        Relay.off(relayIndex);
        delay(RELAY_PULSE_MS);
        // relais reste latchisé OUVERT — pas de Relay.on() ici
    }
}
