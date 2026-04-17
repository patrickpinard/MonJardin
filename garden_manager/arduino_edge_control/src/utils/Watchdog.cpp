#include "Watchdog.h"
#include <mbed.h>

// Watchdog matériel via l'API mbed (Edge Control est basé sur mbed)
static mbed::Watchdog* _wd = nullptr;

void Watchdog::begin(uint32_t timeoutMs) {
    _wd = &mbed::Watchdog::get_instance();
    _wd->start(timeoutMs);
    Serial.print("Watchdog démarré (timeout=");
    Serial.print(timeoutMs);
    Serial.println("ms)");
}

void Watchdog::feed() {
    if (_wd) _wd->kick();
}
