#pragma once
#include <Arduino.h>
#include "../config.h"

// Surveille la fréquence d'arrosage par zone.
// Déclenche une alerte si trop d'arrosages en peu de temps.
class IrrigationGuard {
public:
    IrrigationGuard();

    // À appeler avant d'ouvrir une vanne. Retourne false si la limite est dépassée.
    bool checkAndRecord(int zoneId);

    // Envoie une alerte email au RPi pour transmission SMTP
    void sendAlert(int zoneId);

    // Remet à zéro les compteurs d'une zone (ex. après reset manuel)
    void resetZone(int zoneId);

private:
    static const int MAX_ZONES = 4;

    struct ZoneStats {
        unsigned long lastOpenMs;          // timestamp dernier arrosage
        unsigned long lastAlertMs;         // timestamp dernière alerte
        int           countLastHour;       // arrosages dans la dernière heure
        unsigned long hourWindowStartMs;   // début de la fenêtre d'une heure
    };

    ZoneStats _stats[MAX_ZONES];
};
