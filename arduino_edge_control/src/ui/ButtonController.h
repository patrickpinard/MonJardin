#pragma once
#include <Arduino.h>
#include <Arduino_EdgeControl.h>
#include "../config.h"

// Callbacks — passés depuis main.cpp
typedef void (*ButtonShortPressCb)();   // appui court : écran suivant
typedef void (*ButtonLongPressCb)();    // appui long  : arrêt d'urgence vannes

class ButtonController {
public:
    ButtonController();

    void begin();
    void onShortPress(ButtonShortPressCb cb) { _shortCb = cb; }
    void onLongPress(ButtonLongPressCb  cb)  { _longCb  = cb; }

    // À appeler dans loop()
    void update();

private:
    ButtonShortPressCb _shortCb;
    ButtonLongPressCb  _longCb;

    bool          _lastRaw;
    bool          _stableState;
    unsigned long _debounceStartMs;
    bool          _debouncing;

    unsigned long _pressStartMs;
    bool          _pressed;
    bool          _longFired;  // évite de déclencher plusieurs fois le long press
};
