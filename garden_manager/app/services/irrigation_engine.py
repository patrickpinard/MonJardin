"""Moteur de décision pour l'irrigation — logique hiérarchique par zone."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

# Seuils de sécurité (°C)
FROST_THRESHOLD = 3.0
HEATWAVE_THRESHOLD = 32.0
# Précipitations déclenchant le report (mm/6h)
RAIN_THRESHOLD_MM = 5.0
# Créneaux d'arrosage préférentiels (heure début, heure fin — exclue)
PREFERRED_WINDOWS: list[tuple[int, int]] = [(6, 9), (19, 21)]
# Facteurs d'ajustement des seuils selon les besoins en eau des légumes
WATER_NEED_FACTOR: dict[str, float] = {"low": 0.8, "medium": 1.0, "high": 1.2}


@dataclass
class IrrigationDecision:
    zone_id: int
    action: str  # "open" | "close" | "skip"
    reason: str
    trigger_type: str  # "auto" | "manual" | "weather" | "frost" | "heatwave" | "schedule"
    moisture_at_trigger: Optional[float] = None


def _in_preferred_window(hour: int) -> bool:
    return any(start <= hour < end for start, end in PREFERRED_WINDOWS)


def _get_max_water_need(zone_id: int) -> str:
    """Retourne le besoin en eau maximal parmi les légumes actifs de la zone."""
    try:
        from ..models import Planting
        plantings = Planting.query.filter_by(zone_id=zone_id, status="active").all()
        order = ["low", "medium", "high"]
        max_need = "medium"
        for p in plantings:
            if p.water_need and order.index(p.water_need) > order.index(max_need):
                max_need = p.water_need
        return max_need
    except Exception as e:
        log.warning("Échec lecture plantings zone %d pour water_need : %s", zone_id, e)
        return "medium"


def evaluate_zone(zone, moisture: float, temperature: float, weather: dict, now: datetime) -> IrrigationDecision:
    """Évalue la décision d'arrosage pour une zone selon la logique prioritaire.

    Args:
        zone: instance Zone SQLAlchemy
        moisture: humidité sol actuelle (%)
        temperature: température extérieure (°C)
        weather: dict conditions météo
        now: datetime courant

    Returns:
        IrrigationDecision avec action et justification en français
    """
    hour = now.hour

    # 1. Mode désactivé
    if zone.irrigation_mode == "disabled":
        return IrrigationDecision(
            zone_id=zone.zone_id, action="skip",
            reason="Zone désactivée — aucune action automatique",
            trigger_type="auto",
        )

    # 2. Mode manuel
    if zone.irrigation_mode == "manual":
        return IrrigationDecision(
            zone_id=zone.zone_id, action="skip",
            reason="Mode manuel — commandes uniquement par l'utilisateur",
            trigger_type="manual",
        )

    # 3. Risque de gel
    frost_risk = weather.get("frost_risk", False)
    if temperature < FROST_THRESHOLD or frost_risk:
        return IrrigationDecision(
            zone_id=zone.zone_id, action="close",
            reason=f"Risque de gel (T={temperature:.1f}°C) — fermeture préventive des vannes",
            trigger_type="frost",
            moisture_at_trigger=moisture,
        )

    # 4. Pluie prévue
    precip_mm = weather.get("precip_mm_6h", 0.0)
    if precip_mm > RAIN_THRESHOLD_MM:
        return IrrigationDecision(
            zone_id=zone.zone_id, action="skip",
            reason=f"Pluie prévue ({precip_mm:.1f} mm/6h) — arrosage reporté",
            trigger_type="weather",
        )

    # 5. Canicule — arroser uniquement le soir
    if temperature > HEATWAVE_THRESHOLD and not _in_preferred_window(hour):
        if hour not in range(20, 22):
            return IrrigationDecision(
                zone_id=zone.zone_id, action="skip",
                reason=f"Canicule (T={temperature:.1f}°C) — arrosage uniquement après 20h",
                trigger_type="heatwave",
            )

    # 6. Calcul du seuil bas ajusté selon besoins des légumes
    water_need = _get_max_water_need(zone.zone_id)
    factor = WATER_NEED_FACTOR.get(water_need, 1.0)
    effective_low = zone.moisture_threshold_low * factor

    # 7. Humidité trop basse → arroser
    if moisture < effective_low:
        window_note = "" if _in_preferred_window(hour) else " (hors créneau optimal)"
        return IrrigationDecision(
            zone_id=zone.zone_id, action="open",
            reason=(
                f"Humidité {moisture:.1f}% < seuil {effective_low:.0f}%"
                f" (besoin légumes : {water_need}){window_note}"
            ),
            trigger_type="auto",
            moisture_at_trigger=moisture,
        )

    # 8. Humidité trop haute → fermer si ouverte
    if moisture >= zone.moisture_threshold_high:
        return IrrigationDecision(
            zone_id=zone.zone_id, action="close",
            reason=f"Humidité {moisture:.1f}% ≥ seuil haut {zone.moisture_threshold_high:.0f}% — arrêt arrosage",
            trigger_type="auto",
            moisture_at_trigger=moisture,
        )

    # 9. Aucune action requise
    return IrrigationDecision(
        zone_id=zone.zone_id, action="skip",
        reason=f"Humidité {moisture:.1f}% dans la plage normale ({zone.moisture_threshold_low:.0f}–{zone.moisture_threshold_high:.0f}%)",
        trigger_type="auto",
    )


def execute_decision(decision: IrrigationDecision, arduino_client, db) -> None:
    """Exécute la décision : commande vanne + log en base."""
    from ..models import IrrigationLog, JournalEntry

    if decision.action == "skip":
        return

    success = arduino_client.set_valve(decision.zone_id, decision.action)

    level = "info" if success else "warning"
    status_txt = "" if success else " [ÉCHEC COMMANDE ARDUINO]"

    entry = JournalEntry(
        level=level,
        message=f"Zone {decision.zone_id} — vanne {decision.action}{status_txt} : {decision.reason}",
    )
    db.session.add(entry)

    if success:
        log_entry = IrrigationLog(
            zone_id=decision.zone_id,
            action=decision.action,
            trigger_type=decision.trigger_type,
            reason=decision.reason,
            moisture_at_trigger=decision.moisture_at_trigger,
        )
        db.session.add(log_entry)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error("Échec persistance décision irrigation zone %d : %s", decision.zone_id, e, exc_info=True)
        return
    log.info("Zone %d vanne %s : %s", decision.zone_id, decision.action, decision.reason)
