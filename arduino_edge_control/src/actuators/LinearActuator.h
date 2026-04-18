#pragma once
#include <Arduino.h>
#include "../config.h"

enum ActuatorState { ACT_CLOSED, ACT_OPEN, ACT_MOVING_OPEN, ACT_MOVING_CLOSE, ACT_ERROR };

class LinearActuator {
public:
    LinearActuator();
    void begin();

    void open();
    void close();
    void stop();

    // À appeler dans loop() — gère timeout et fins de course
    void update();

    ActuatorState state() const { return _state; }
    const char* stateStr() const;

private:
    ActuatorState  _state;
    unsigned long  _moveStartMs;

    bool _endstopOpen()  const { return digitalRead(ENDSTOP_OPEN)  == LOW; }
    bool _endstopClose() const { return digitalRead(ENDSTOP_CLOSE) == LOW; }
};
