#pragma once
#include <Arduino.h>
#include "../config.h"

// Données capteurs passées à l'affichage à chaque cycle
struct DisplayData {
    float moisture[4];     // % humidité zones 1-4
    bool  valveOpen[4];    // état vannes 1-4
    float tempExt;         // °C extérieur
    float tempSerre;       // °C serre
    float windKmh;         // km/h vent
    bool  wifiOk;
    bool  rpiOk;
    unsigned long uptimeS;
};

enum LcdScreen {
    SCREEN_ZONE_12 = 0,    // humidité zones 1 et 2
    SCREEN_ZONE_34,        // humidité zones 3 et 4
    SCREEN_CLIMATE,        // températures + vent
    SCREEN_VALVES,         // état des 4 vannes
    SCREEN_SYSTEM,         // WiFi / RPi / uptime
    SCREEN_COUNT
};

class DisplayController {
public:
    DisplayController();

    void begin();

    // Mise à jour des données — appeler à chaque cycle capteurs
    void setData(const DisplayData& d);

    // Avance manuellement à l'écran suivant (appui bouton)
    void nextScreen();

    // Affiche un message d'alerte urgent pendant alertDurationMs, puis reprend
    void showAlert(const char* line1, const char* line2, unsigned long alertDurationMs = 3000);

    // À appeler dans loop() — gère la rotation et le backlight
    void update();

    LcdScreen currentScreen() const { return _screen; }

private:
    DisplayData   _data;
    LcdScreen     _screen;
    unsigned long _lastScreenChangeMs;
    unsigned long _lastActivityMs;
    bool          _alertActive;
    unsigned long _alertEndMs;
    bool          _backlightOn;

    void _render();
    void _renderZone12();
    void _renderZone34();
    void _renderClimate();
    void _renderValves();
    void _renderSystem();

    // Formate "XX.X%" sur exactement 5 chars pour alignement
    static void _formatMoisture(float pct, char* buf5);
};
