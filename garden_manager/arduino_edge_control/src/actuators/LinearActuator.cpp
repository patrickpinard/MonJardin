#include "LinearActuator.h"
#include "../config.h"

// États internes
#define STATE_CLOSE       0
#define STATE_OPEN        1
#define STATE_MOVING_OPEN 2
#define STATE_MOVING_CLOSE 3
#define STATE_UNKNOWN     4

LinearActuator::LinearActuator(uint8_t in1, uint8_t in2,
                                uint8_t endstopOpen, uint8_t endstopClose)
    : _in1(in1), _in2(in2),
      _endstopOpen(endstopOpen), _endstopClose(endstopClose),
      _moveStartMs(0), _state(STATE_UNKNOWN) {}

void LinearActuator::begin() {
    pinMode(_in1, OUTPUT);
    pinMode(_in2, OUTPUT);
    pinMode(_endstopOpen, INPUT_PULLUP);
    pinMode(_endstopClose, INPUT_PULLUP);
    stop();
    // Détermine l'état initial via les fins de course
    if (digitalRead(_endstopClose) == LOW) {
        _state = STATE_CLOSE;
    } else if (digitalRead(_endstopOpen) == LOW) {
        _state = STATE_OPEN;
    } else {
        // Position inconnue — fermer par sécurité
        close();
    }
}

void LinearActuator::open() {
    if (_state == STATE_OPEN) return;
    _applyDirection(true, false);  // IN1=HIGH, IN2=LOW
    _state = STATE_MOVING_OPEN;
    _moveStartMs = millis();
}

void LinearActuator::close() {
    if (_state == STATE_CLOSE) return;
    _applyDirection(false, true);  // IN1=LOW, IN2=HIGH
    _state = STATE_MOVING_CLOSE;
    _moveStartMs = millis();
}

void LinearActuator::stop() {
    _applyDirection(false, false);
}

void LinearActuator::update() {
    if (_state != STATE_MOVING_OPEN && _state != STATE_MOVING_CLOSE) return;

    // Vérification fins de course (actifs bas avec pull-up)
    bool atOpen  = (digitalRead(_endstopOpen) == LOW);
    bool atClose = (digitalRead(_endstopClose) == LOW);

    if (_state == STATE_MOVING_OPEN && atOpen) {
        stop();
        _state = STATE_OPEN;
    } else if (_state == STATE_MOVING_CLOSE && atClose) {
        stop();
        _state = STATE_CLOSE;
    } else if (millis() - _moveStartMs > ACTUATOR_TIMEOUT_MS) {
        // Timeout — arrêt de sécurité (fin de course jamais atteinte)
        stop();
        _state = STATE_UNKNOWN;
    }
}

bool LinearActuator::isMoving() const {
    return _state == STATE_MOVING_OPEN || _state == STATE_MOVING_CLOSE;
}

const char* LinearActuator::getState() const {
    switch (_state) {
        case STATE_OPEN:         return "open";
        case STATE_CLOSE:        return "close";
        case STATE_MOVING_OPEN:
        case STATE_MOVING_CLOSE: return "moving";
        default:                 return "unknown";
    }
}

void LinearActuator::_applyDirection(bool forward, bool reverse) {
    digitalWrite(_in1, forward  ? HIGH : LOW);
    digitalWrite(_in2, reverse  ? HIGH : LOW);
}
