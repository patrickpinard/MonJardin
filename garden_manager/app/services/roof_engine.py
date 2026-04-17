"""Moteur de décision pour le toit de la serre (Zone 1 uniquement)."""
import logging
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)

# Seuils toit
ROOF_OPEN_TEMP_MIN = 25.0       # °C — ouvrir au dessus de cette température
ROOF_CLOSE_TEMP_MAX = 8.0       # °C — fermer en dessous de cette température
ROOF_CLOSE_WIND_KMH = 40.0      # km/h — fermer si vent fort
ROOF_OPEN_MOISTURE_MAX = 75.0   # % — ventiler si sol trop humide
ROOF_CLOSE_PRECIP_PROB = 50.0   # % probabilité pluie → fermer
ROOF_CLOSE_PRECIP_MM = 0.5      # mm — pluie en cours → fermer
# Fermeture nocturne en période froide (octobre à mars)
ROOF_NIGHTTIME_CLOSE_HOUR = 21
COLD_MONTHS = {10, 11, 12, 1, 2, 3}


@dataclass
class RoofDecision:
    action: str   # "open" | "close" | "maintain"
    reason: str
    trigger_type: str  # "auto" | "manual" | "weather" | "temperature"


def evaluate_roof(zone1_moisture: float, temperature: float, weather: dict,
                  now: datetime, current_state: str) -> RoofDecision:
    """Évalue si le toit doit être ouvert, fermé ou maintenu.

    Priorité : fermeture > ouverture > maintien.
    Par défaut (démarrage) : FERMÉ (sécurité).
    """
    hour = now.hour
    month = now.month

    # --- Conditions de FERMETURE (priorité haute) ---

    if weather.get("frost_risk", False) or temperature < ROOF_CLOSE_TEMP_MAX:
        return RoofDecision(
            action="close",
            reason=f"Protection gel/froid (T={temperature:.1f}°C) — toit fermé",
            trigger_type="temperature",
        )

    precip_prob = weather.get("precip_prob_pct", 0.0)
    precip_mm = weather.get("precip_mm_6h", 0.0)
    if precip_prob >= ROOF_CLOSE_PRECIP_PROB or precip_mm >= ROOF_CLOSE_PRECIP_MM:
        return RoofDecision(
            action="close",
            reason=f"Pluie prévue ({precip_prob:.0f}% / {precip_mm:.1f} mm) — toit fermé",
            trigger_type="weather",
        )

    wind = weather.get("wind_kmh", 0.0)
    if wind > ROOF_CLOSE_WIND_KMH:
        return RoofDecision(
            action="close",
            reason=f"Vent fort ({wind:.0f} km/h) — protection structure",
            trigger_type="weather",
        )

    # Fermeture nocturne en saison froide
    if month in COLD_MONTHS and hour >= ROOF_NIGHTTIME_CLOSE_HOUR:
        return RoofDecision(
            action="close",
            reason=f"Nuit en période froide (mois {month}, {hour}h) — toit fermé",
            trigger_type="auto",
        )

    # --- Conditions d'OUVERTURE ---

    if temperature >= ROOF_OPEN_TEMP_MIN and precip_prob < ROOF_CLOSE_PRECIP_PROB:
        return RoofDecision(
            action="open",
            reason=f"Température {temperature:.1f}°C ≥ {ROOF_OPEN_TEMP_MIN}°C, pas de pluie — aération serre",
            trigger_type="temperature",
        )

    if zone1_moisture > ROOF_OPEN_MOISTURE_MAX:
        return RoofDecision(
            action="open",
            reason=f"Humidité zone 1 élevée ({zone1_moisture:.1f}%) — ventilation nécessaire",
            trigger_type="auto",
        )

    # Maintien de l'état actuel
    return RoofDecision(
        action="maintain",
        reason=f"Conditions normales — maintien état {current_state}",
        trigger_type="auto",
    )


def execute_roof_decision(decision: RoofDecision, arduino_client, db) -> None:
    """Exécute la décision toit : commande vérin + log."""
    from ..models import RoofLog, JournalEntry

    if decision.action == "maintain":
        return

    success = arduino_client.set_roof(decision.action)

    level = "info" if success else "warning"
    status_txt = "" if success else " [ÉCHEC COMMANDE ARDUINO]"

    entry = JournalEntry(
        level=level,
        message=f"Lucarne — {decision.action}{status_txt} : {decision.reason}",
    )
    db.session.add(entry)

    if success:
        log_entry = RoofLog(
            action=decision.action,
            trigger_type=decision.trigger_type,
            reason=decision.reason,
        )
        db.session.add(log_entry)

    db.session.commit()
    log.info("Lucarne %s : %s", decision.action, decision.reason)
