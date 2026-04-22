"""Initialisation des données par défaut et historique de démonstration."""
import logging
import math
import random
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

# Humidités de départ par zone (%)
INITIAL_MOISTURE = {1: 65.0, 2: 72.0, 3: 58.0, 4: 45.0}
# Taux d'évaporation par zone (%/heure)
DRAIN_RATES_HR = {1: 1.0, 2: 1.8, 3: 1.4, 4: 2.5}
# Température de base pour l'historique simulé (°C)
T_BASE = 18.0
T_AMP = 8.0


def ensure_defaults(app) -> None:
    """Insère les 4 zones si absentes."""
    from .models import db, Zone

    with app.app_context():
        if Zone.query.count() > 0:
            return

        zones = [
            Zone(zone_id=1, name="Serre", description="Zone couverte avec toiture rétractable (vérin)",
                 has_roof=True, irrigation_mode="auto",
                 moisture_threshold_low=30.0, moisture_threshold_high=65.0, irrigation_duration_min=15),
            Zone(zone_id=2, name="Soleil", description="Plein terre, exposition plein sud",
                 has_roof=False, irrigation_mode="auto",
                 moisture_threshold_low=30.0, moisture_threshold_high=65.0, irrigation_duration_min=15),
            Zone(zone_id=3, name="Mi-ombre", description="Plein terre, partiellement ombragée",
                 has_roof=False, irrigation_mode="auto",
                 moisture_threshold_low=30.0, moisture_threshold_high=65.0, irrigation_duration_min=15),
            Zone(zone_id=4, name="Aromates", description="Plein terre, herbes et aromatiques",
                 has_roof=False, irrigation_mode="auto",
                 moisture_threshold_low=25.0, moisture_threshold_high=55.0, irrigation_duration_min=10),
        ]
        db.session.bulk_save_objects(zones)
        db.session.commit()
        log.info("Zones par défaut créées.")


def seed_demo_history(app, hours: int = 720) -> None:
    """Génère un historique de démonstration sur N heures."""
    from .models import db, SensorReading, IrrigationLog

    with app.app_context():
        # Minimum attendu : 25 jours × 4 zones × 4 relevés/h = 9600
        if SensorReading.query.count() >= 9600:
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        start = now - timedelta(hours=hours)
        interval_min = 15
        readings = []
        irr_logs = []

        # État courant par zone
        moisture = dict(INITIAL_MOISTURE)
        valve_open = {z: False for z in range(1, 5)}
        irrigation_start = {}

        steps = int(hours * 60 / interval_min)

        for step in range(steps):
            ts = start + timedelta(minutes=step * interval_min)
            dt_hr = interval_min / 60.0
            hour = ts.hour + ts.minute / 60.0
            temp = T_BASE + T_AMP * math.sin((hour - 14) * math.pi / 12)
            temp += random.gauss(0, 0.3)

            for z in range(1, 5):
                # Évaporation
                drain = DRAIN_RATES_HR[z] * dt_hr
                # Plus chaud = plus d'évaporation
                drain *= 1.0 + max(0.0, (temp - 20.0) / 20.0)
                moisture[z] -= drain + random.gauss(0, 0.1)
                moisture[z] = max(5.0, min(98.0, moisture[z]))

                # Arrosage si humidité trop basse
                threshold_low = 30.0 if z != 4 else 25.0
                threshold_high = 65.0 if z != 4 else 55.0
                if not valve_open[z] and moisture[z] < threshold_low:
                    valve_open[z] = True
                    irrigation_start[z] = ts
                    irr_logs.append(IrrigationLog(
                        timestamp=ts, zone_id=z, action="open",
                        trigger_type="auto",
                        reason=f"Humidité {moisture[z]:.1f}% < seuil {threshold_low:.0f}%",
                        moisture_at_trigger=moisture[z],
                    ))
                if valve_open[z]:
                    moisture[z] += 2.4 * dt_hr  # +2.4%/heure quand vanne ouverte
                    if moisture[z] >= threshold_high:
                        valve_open[z] = False
                        duration = int((ts - irrigation_start.get(z, ts)).total_seconds())
                        irr_logs.append(IrrigationLog(
                            timestamp=ts, zone_id=z, action="close",
                            trigger_type="auto",
                            reason=f"Humidité {moisture[z]:.1f}% ≥ seuil haut {threshold_high:.0f}%",
                            moisture_at_trigger=moisture[z],
                            duration_seconds=duration,
                        ))

                readings.append(SensorReading(
                    timestamp=ts,
                    zone_id=z,
                    soil_moisture_pct=round(moisture[z], 2),
                    raw_adc=round(moisture[z] / 100.0 * 4095),
                    temperature_c=round(temp, 2),
                    is_simulated=True,
                ))

        db.session.bulk_save_objects(readings)
        db.session.bulk_save_objects(irr_logs)
        db.session.commit()
        log.info("Historique démo généré : %d relevés sur %dh.", len(readings), hours)
