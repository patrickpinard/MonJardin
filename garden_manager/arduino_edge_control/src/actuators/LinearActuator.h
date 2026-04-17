#pragma once
#include <Arduino.h>

// Pilotage vérin linéaire 12V via H-bridge (2 pins direction + 2 fins de course)
class LinearActuator {
public:
    LinearActuator(uint8_t in1, uint8_t in2, uint8_t endstopOpen, uint8_t endstopClose);
    void begin();

    // Lance le mouvement (non bloquant — appeler update() dans loop())
    void open();
    void close();
    void stop();

    // À appeler dans loop() pour surveiller les fins de course
    void update();

    bool isMoving() const;
    // Retourne "open", "close", "moving", ou "unknown"
    const char* getState() const;

private:
    uint8_t _in1, _in2;
    uint8_t _endstopOpen, _endstopClose;
    unsigned long _moveStartMs;
    uint8_t _state;  // 0=close, 1=open, 2=moving_open, 3=moving_close, 4=unknown

    void _applyDirection(bool forward, bool reverse);
};
