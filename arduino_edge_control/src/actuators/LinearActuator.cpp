#include "LinearActuator.h"
#include "../utils/Logger.h"

LinearActuator::LinearActuator() : _state(ACT_CLOSED), _moveStartMs(0) {}

void LinearActuator::begin() {
    pinMode(ACTUATOR_IN1, OUTPUT);
    pinMode(ACTUATOR_IN2, OUTPUT);
    pinMode(ENDSTOP_OPEN,  INPUT_PULLUP);
    pinMode(ENDSTOP_CLOSE, INPUT_PULLUP);
    stop();
    Logger::log(LOG_INFO, "ACTUATOR", "Vérin initialisé");
}

void LinearActuator::open() {
    if (_state == ACT_OPEN || _state == ACT_MOVING_OPEN) return;
    if (_endstopOpen()) { _state = ACT_OPEN; return; }
    Logger::log(LOG_INFO, "ACTUATOR", "Lucarne -> ouverture");
    digitalWrite(ACTUATOR_IN1, HIGH);
    digitalWrite(ACTUATOR_IN2, LOW);
    _state = ACT_MOVING_OPEN;
    _moveStartMs = millis();
}

void LinearActuator::close() {
    if (_state == ACT_CLOSED || _state == ACT_MOVING_CLOSE) return;
    if (_endstopClose()) { _state = ACT_CLOSED; return; }
    Logger::log(LOG_INFO, "ACTUATOR", "Lucarne -> fermeture");
    digitalWrite(ACTUATOR_IN1, LOW);
    digitalWrite(ACTUATOR_IN2, HIGH);
    _state = ACT_MOVING_CLOSE;
    _moveStartMs = millis();
}

void LinearActuator::stop() {
    digitalWrite(ACTUATOR_IN1, LOW);
    digitalWrite(ACTUATOR_IN2, LOW);
}

void LinearActuator::update() {
    if (_state == ACT_MOVING_OPEN) {
        if (_endstopOpen()) {
            stop();
            _state = ACT_OPEN;
            Logger::log(LOG_INFO, "ACTUATOR", "Lucarne ouverte (fin de course)");
        } else if (millis() - _moveStartMs > ACTUATOR_TIMEOUT_MS) {
            stop();
            _state = ACT_ERROR;
            Logger::log(LOG_ERROR, "ACTUATOR", "Timeout ouverture lucarne — arrêt forcé");
        }
    } else if (_state == ACT_MOVING_CLOSE) {
        if (_endstopClose()) {
            stop();
            _state = ACT_CLOSED;
            Logger::log(LOG_INFO, "ACTUATOR", "Lucarne fermée (fin de course)");
        } else if (millis() - _moveStartMs > ACTUATOR_TIMEOUT_MS) {
            stop();
            _state = ACT_ERROR;
            Logger::log(LOG_ERROR, "ACTUATOR", "Timeout fermeture lucarne — arrêt forcé");
        }
    }
}

const char* LinearActuator::stateStr() const {
    switch (_state) {
        case ACT_CLOSED:       return "close";
        case ACT_OPEN:         return "open";
        case ACT_MOVING_OPEN:  return "moving_open";
        case ACT_MOVING_CLOSE: return "moving_close";
        case ACT_ERROR:        return "error";
        default:               return "unknown";
    }
}
