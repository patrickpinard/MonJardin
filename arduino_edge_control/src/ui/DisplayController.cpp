#include "DisplayController.h"
#include <Arduino_EdgeControl.h>
#include <stdio.h>
#include <string.h>

DisplayController::DisplayController()
    : _screen(SCREEN_ZONE_12),
      _lastScreenChangeMs(0),
      _lastActivityMs(0),
      _alertActive(false),
      _alertEndMs(0),
      _backlightOn(true)
{
    memset(&_data, 0, sizeof(_data));
    for (int i = 0; i < 4; i++) _data.moisture[i] = -1.0f;
    _data.tempExt   = -127.0f;
    _data.tempSerre = -127.0f;
}

void DisplayController::begin() {
    LCD.begin(LCD_COLS, LCD_ROWS);
    LCD.backlight();
    _backlightOn     = true;
    _lastActivityMs  = millis();
    _lastScreenChangeMs = millis();

    // Écran de démarrage
    LCD.clear();
    LCD.setCursor(0, 0);
    LCD.print("  MonJardin v1  ");
    LCD.setCursor(0, 1);
    LCD.print("  Demarrage...  ");
}

void DisplayController::setData(const DisplayData& d) {
    _data = d;
}

void DisplayController::nextScreen() {
    _screen = (LcdScreen)(((int)_screen + 1) % SCREEN_COUNT);
    _lastScreenChangeMs = millis();
    _lastActivityMs     = millis();

    // Réallume le backlight à chaque interaction
    if (!_backlightOn) {
        LCD.backlight();
        _backlightOn = true;
    }
    _render();
}

void DisplayController::showAlert(const char* line1, const char* line2, unsigned long alertDurationMs) {
    _alertActive  = true;
    _alertEndMs   = millis() + alertDurationMs;
    _lastActivityMs = millis();

    if (!_backlightOn) { LCD.backlight(); _backlightOn = true; }

    LCD.clear();
    // Centrage simple sur 16 caractères
    char buf[17];
    snprintf(buf, sizeof(buf), "%-16s", line1);
    LCD.setCursor(0, 0);
    LCD.print(buf);
    snprintf(buf, sizeof(buf), "%-16s", line2);
    LCD.setCursor(0, 1);
    LCD.print(buf);
}

void DisplayController::update() {
    unsigned long now = millis();

    // Fin d'alerte → revenir à la rotation
    if (_alertActive && now >= _alertEndMs) {
        _alertActive = false;
        _render();
    }
    if (_alertActive) return;

    // Rotation automatique des écrans
    if (now - _lastScreenChangeMs >= LCD_SCREEN_INTERVAL_MS) {
        _screen = (LcdScreen)(((int)_screen + 1) % SCREEN_COUNT);
        _lastScreenChangeMs = now;
        _render();
    }

    // Gestion rétroéclairage
    if (_backlightOn && (now - _lastActivityMs >= LCD_BACKLIGHT_MS)) {
        LCD.noBacklight();
        _backlightOn = false;
    }
}

// ── Rendu ────────────────────────────────────────────────��───────────────

void DisplayController::_render() {
    LCD.clear();
    switch (_screen) {
        case SCREEN_ZONE_12:  _renderZone12();  break;
        case SCREEN_ZONE_34:  _renderZone34();  break;
        case SCREEN_CLIMATE:  _renderClimate(); break;
        case SCREEN_VALVES:   _renderValves();  break;
        case SCREEN_SYSTEM:   _renderSystem();  break;
        default: break;
    }
}

void DisplayController::_renderZone12() {
    // Ligne 0 : "Z1:XX.X%  Z2:XX.X%"  (tronqué à 16)
    // Format : "Z1: 65%  Z2: 43%"
    char m1[6], m2[6];
    _formatMoisture(_data.moisture[0], m1);
    _formatMoisture(_data.moisture[1], m2);

    char line[17];
    snprintf(line, sizeof(line), "Z1:%-5s Z2:%-5s", m1, m2);
    LCD.setCursor(0, 0);
    LCD.print(line);

    // Ligne 1 : état vannes + indicateurs
    char vl[17];
    snprintf(vl, sizeof(vl), "V1:%s  V2:%s   ",
        _data.valveOpen[0] ? "ON " : "OFF",
        _data.valveOpen[1] ? "ON " : "OFF");
    LCD.setCursor(0, 1);
    LCD.print(vl);
}

void DisplayController::_renderZone34() {
    char m3[6], m4[6];
    _formatMoisture(_data.moisture[2], m3);
    _formatMoisture(_data.moisture[3], m4);

    char line[17];
    snprintf(line, sizeof(line), "Z3:%-5s Z4:%-5s", m3, m4);
    LCD.setCursor(0, 0);
    LCD.print(line);

    char vl[17];
    snprintf(vl, sizeof(vl), "V3:%s  V4:%s   ",
        _data.valveOpen[2] ? "ON " : "OFF",
        _data.valveOpen[3] ? "ON " : "OFF");
    LCD.setCursor(0, 1);
    LCD.print(vl);
}

void DisplayController::_renderClimate() {
    // Ligne 0 : températures
    char line0[17];
    if (_data.tempExt > -100.0f && _data.tempSerre > -100.0f) {
        snprintf(line0, sizeof(line0), "Ext%+5.1fSer%+5.1f",
            _data.tempExt, _data.tempSerre);
    } else if (_data.tempExt > -100.0f) {
        snprintf(line0, sizeof(line0), "Ext: %+6.1f C    ", _data.tempExt);
    } else {
        snprintf(line0, sizeof(line0), "Temp: ---       ");
    }
    LCD.setCursor(0, 0);
    LCD.print(line0);

    // Ligne 1 : vent
    char line1[17];
    snprintf(line1, sizeof(line1), "Vent: %5.1f km/h", _data.windKmh);
    LCD.setCursor(0, 1);
    LCD.print(line1);
}

void DisplayController::_renderValves() {
    // Ligne 0 : V1 V2 V3 V4 avec état
    LCD.setCursor(0, 0);
    LCD.print("Vannes:         ");
    char line[17];
    snprintf(line, sizeof(line), "%s %s %s %s      ",
        _data.valveOpen[0] ? "V1" : "--",
        _data.valveOpen[1] ? "V2" : "--",
        _data.valveOpen[2] ? "V3" : "--",
        _data.valveOpen[3] ? "V4" : "--");
    LCD.setCursor(0, 1);
    LCD.print(line);
}

void DisplayController::_renderSystem() {
    // Ligne 0 : WiFi + RPi
    char line0[17];
    snprintf(line0, sizeof(line0), "WiFi:%s RPi:%s  ",
        _data.wifiOk ? "OK " : "OFF",
        _data.rpiOk  ? "OK " : "OFF");
    LCD.setCursor(0, 0);
    LCD.print(line0);

    // Ligne 1 : uptime en h:mm
    unsigned long h  = _data.uptimeS / 3600;
    unsigned long m  = (_data.uptimeS % 3600) / 60;
    char line1[17];
    snprintf(line1, sizeof(line1), "Uptime: %4luh%02lum", h, m);
    LCD.setCursor(0, 1);
    LCD.print(line1);
}

void DisplayController::_formatMoisture(float pct, char* buf5) {
    if (pct < 0.0f) {
        strncpy(buf5, "---  ", 6);
    } else {
        snprintf(buf5, 6, "%3d%% ", (int)pct);
    }
}
