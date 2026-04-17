#pragma once
#include <Arduino.h>
#include <Arduino_EdgeControl.h>

// Pilotage vanne solénoïde 24V via relais latching
class ValveController {
public:
    // relayIndex : index sur le module relais Edge Control (0-based)
    explicit ValveController(uint8_t relayIndex);
    void begin();
    void open();
    void close();
    bool isOpen() const;
    const char* getState() const;  // "open" ou "close"

private:
    uint8_t _relayIndex;
    bool    _isOpen;
    // Envoie une impulsion courte au relais latching
    void _pulse(bool openRelay);
};
