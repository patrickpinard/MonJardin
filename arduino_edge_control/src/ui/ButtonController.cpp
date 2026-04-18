#include "ButtonController.h"

ButtonController::ButtonController()
    : _shortCb(nullptr), _longCb(nullptr),
      _lastRaw(HIGH), _stableState(HIGH),
      _debounceStartMs(0), _debouncing(false),
      _pressStartMs(0), _pressed(false), _longFired(false)
{}

void ButtonController::begin() {
    pinMode(BUTTON_PIN, INPUT_PULLUP);
}

void ButtonController::update() {
    unsigned long now = millis();
    bool raw = digitalRead(BUTTON_PIN);

    // ── Anti-rebond ────────────────────────────────────────────────────────
    if (raw != _lastRaw) {
        _debounceStartMs = now;
        _debouncing      = true;
        _lastRaw         = raw;
    }
    if (_debouncing && (now - _debounceStartMs >= BUTTON_DEBOUNCE_MS)) {
        _debouncing = false;
        _stableState = raw;
    }

    // ── Détection appui / relâchement ──────────────────────────────────────
    bool buttonDown = (_stableState == LOW);  // INPUT_PULLUP → LOW = appuyé

    if (buttonDown && !_pressed) {
        // Front descendant : début de l'appui
        _pressed       = true;
        _longFired     = false;
        _pressStartMs  = now;
    }

    if (_pressed && buttonDown && !_longFired) {
        // Maintien : vérifier si appui long atteint
        if (now - _pressStartMs >= BUTTON_LONG_PRESS_MS) {
            _longFired = true;
            if (_longCb) _longCb();
        }
    }

    if (!buttonDown && _pressed) {
        // Front montant : relâchement
        if (!_longFired) {
            // Appui court (pas encore déclenché le long press)
            if (_shortCb) _shortCb();
        }
        _pressed   = false;
        _longFired = false;
    }
}
