"""Tâches planifiées APScheduler : cycle d'automatisation et météo."""
import logging
from datetime import datetime

log = logging.getLogger(__name__)


def automation_cycle(app) -> None:
    """Cycle principal : lecture capteurs → décisions irrigation + toit."""
    with app.app_context():
        try:
            _run_cycle(app)
        except Exception as e:
            log.error("Erreur cycle automatisation : %s", e, exc_info=True)


def _run_cycle(app) -> None:
    from ..models import db, SensorReading, Zone, JournalEntry
    from .arduino_client import ArduinoClient
    from .weather_service import WeatherService
    from . import irrigation_engine, roof_engine

    arduino: ArduinoClient = app.extensions["arduino_client"]
    weather_svc: WeatherService = app.extensions["weather_service"]

    # 1. Lecture capteurs
    sensor_data = arduino.get_all_sensors()
    if sensor_data is None:
        log.warning("Arduino injoignable — cycle ignoré (échecs consécutifs : %d)",
                    arduino.consecutive_failures)
        # Failsafe : si > 10 échecs consécutifs, fermer les vannes
        if arduino.consecutive_failures > 10:
            _emergency_close(app)
        return

    # 2. Persistance en base
    now = datetime.utcnow()
    temp = sensor_data.get("temperature_c", 15.0)
    temp_serre = sensor_data.get("temp_serre_c")
    zones_data = {z["zone_id"]: z for z in sensor_data.get("zones", [])}

    for zone_id in range(1, 5):
        z_data = zones_data.get(zone_id)
        if z_data:
            reading = SensorReading(
                timestamp=now,
                zone_id=zone_id,
                soil_moisture_pct=z_data.get("soil_moisture_pct"),
                raw_adc=z_data.get("raw_adc"),
                temperature_c=temp,
                temp_serre_c=temp_serre,
                is_simulated=app.config.get("SIMULATION_MODE", False),
            )
            db.session.add(reading)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error("Échec persistance SensorReadings : %s", e, exc_info=True)
        return

    # 3. Météo
    weather = weather_svc.get_current()

    # 4. Moteur irrigation par zone
    zones = Zone.query.order_by(Zone.zone_id).all()
    for zone in zones:
        z_data = zones_data.get(zone.zone_id)
        if z_data is None:
            log.warning("Pas de données capteur pour la zone %d — ignorée", zone.zone_id)
            continue
        moisture = z_data.get("soil_moisture_pct", 50.0)
        decision = irrigation_engine.evaluate_zone(zone, moisture, temp, weather, now)
        if decision.action != "skip":
            irrigation_engine.execute_decision(decision, arduino, db)

    # 5. Moteur toit (Zone 1 uniquement)
    z1_data = zones_data.get(1)
    if z1_data:
        z1_moisture = z1_data.get("soil_moisture_pct", 50.0)
        actuator_status = arduino.get_actuator_status() or {}
        current_roof = actuator_status.get("roof_state", "close")
        roof_decision = roof_engine.evaluate_roof(z1_moisture, temp, weather, now, current_roof)
        if roof_decision.action != "maintain":
            roof_engine.execute_roof_decision(roof_decision, arduino, db)

    log.debug("Cycle automatisation terminé à %s", now.isoformat())


def _emergency_close(app) -> None:
    """Ferme toutes les vannes en cas de perte prolongée de connexion Arduino."""
    from ..models import db, JournalEntry
    from .arduino_client import ArduinoClient

    arduino: ArduinoClient = app.extensions["arduino_client"]
    for zone_id in range(1, 5):
        ok = arduino.set_valve(zone_id, "close")
        if not ok:
            log.error("FAILSAFE : échec fermeture vanne zone %d", zone_id)
    ok_roof = arduino.set_roof("close")
    if not ok_roof:
        log.error("FAILSAFE : échec fermeture lucarne")

    try:
        entry = JournalEntry(
            level="warning",
            message="Failsafe : Arduino injoignable depuis trop longtemps — fermeture de toutes les vannes et de la lucarne",
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error("FAILSAFE : échec écriture journal : %s", e)
    log.warning("FAILSAFE : vannes et lucarne fermées (perte connexion Arduino).")


def weather_poll(app) -> None:
    """Rafraîchit le cache météo."""
    with app.app_context():
        try:
            from .weather_service import WeatherService
            weather_svc: WeatherService = app.extensions["weather_service"]
            data = weather_svc.get_current()
            log.debug("Météo rafraîchie : source=%s T=%.1f°C", data.get("source"), data.get("temperature", 0))
        except Exception as e:
            log.warning("Erreur rafraîchissement météo : %s", e)
