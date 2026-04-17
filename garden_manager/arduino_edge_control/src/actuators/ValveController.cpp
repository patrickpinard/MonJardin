#include "ValveController.h"
#include "../config.h"

ValveController::ValveController(uint8_t relayIndex)
    : _relayIndex(relayIndex), _isOpen(false) {}

void ValveController::begin() {
    // Sécurité au démarrage : s'assurer que la vanne est fermée
    close();
}

void ValveController::open() {
    if (_isOpen) return;
    _pulse(true);
    _isOpen = true;
}

void ValveController::close() {
    if (!_isOpen && _relayIndex != 255) {
        // Forcer la fermeture même si l'état interne dit "fermé" (démarrage)
    }
    _pulse(false);
    _isOpen = false;
}

bool ValveController::isOpen() const {
    return _isOpen;
}

const char* ValveController::getState() const {
    return _isOpen ? "open" : "close";
}

void ValveController::_pulse(bool openRelay) {
    // Les relais latching du Edge Control utilisent deux bobines :
    // SET (ouverture) et RESET (fermeture) — impulsion courte suffisante
    if (openRelay) {
        Relay.on(_relayIndex);
    } else {
        Relay.off(_relayIndex);
    }
    delay(RELAY_PULSE_MS);
    // Pour les relais latching, couper l'alimentation après l'impulsion
    // (la position est mémorisée mécaniquement)
    Relay.off(_relayIndex);
}
