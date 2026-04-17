"""Émulateur complet de l'API REST de l'Arduino Edge Control.

Expose exactement les mêmes endpoints que le vrai Arduino sur un port séparé.
Utilisé uniquement quand SIMULATION_MODE=true.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

from .sensor_simulator import SensorSimulator
from .actuator_simulator import ActuatorSimulator
from .weather_simulator import WeatherSimulator

log = logging.getLogger(__name__)

_emulator_app = Flask(__name__)
CORS(_emulator_app)

_sensor_sim: SensorSimulator = None  # type: ignore[assignment]
_actuator_sim: ActuatorSimulator = None  # type: ignore[assignment]
_weather_sim: WeatherSimulator = None  # type: ignore[assignment]
_start_time: float = time.time()


def _init_simulators(speed: float, weather_profile: str) -> None:
    global _sensor_sim, _actuator_sim, _weather_sim
    _sensor_sim = SensorSimulator(speed=speed, weather_profile=weather_profile)
    _actuator_sim = ActuatorSimulator(sensor_sim=_sensor_sim)
    _weather_sim = WeatherSimulator(profile=weather_profile)


# ---------------------------------------------------------------------------
# Endpoints Arduino (miroirs exacts)
# ---------------------------------------------------------------------------

@_emulator_app.get("/api/sensors")
def get_sensors():
    """Toutes les mesures capteurs."""
    _sensor_sim.tick()
    data = _sensor_sim.snapshot()
    return jsonify({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": data["temperature_c"],
        "temp_serre_c": data.get("temp_serre_c"),
        "zones": data["zones"],
    })


@_emulator_app.get("/api/sensors/<int:zone_id>")
def get_zone_sensor(zone_id: int):
    """Mesure d'une zone spécifique."""
    _sensor_sim.tick()
    data = _sensor_sim.snapshot()
    zone = next((z for z in data["zones"] if z["zone_id"] == zone_id), None)
    if zone is None:
        return jsonify({"error": f"Zone {zone_id} non disponible"}), 404
    return jsonify({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": data["temperature_c"],
        "zone": zone,
    })


@_emulator_app.get("/api/actuators/status")
def get_actuator_status():
    """État de toutes les vannes et du vérin."""
    return jsonify(_actuator_sim.get_all_status())


@_emulator_app.post("/api/actuators/valve/<int:zone_id>")
def set_valve(zone_id: int):
    """Ouvrir/fermer une vanne."""
    body = request.get_json(silent=True) or {}
    state = body.get("state", "")
    if state not in ("open", "close"):
        return jsonify({"ok": False, "error": "state doit être 'open' ou 'close'"}), 400
    result = _actuator_sim.set_valve(zone_id, state)
    status_code = 200 if result["ok"] else 500
    return jsonify(result), status_code


@_emulator_app.post("/api/actuators/roof")
def set_roof():
    """Ouvrir/fermer le toit de la serre."""
    body = request.get_json(silent=True) or {}
    state = body.get("state", "")
    if state not in ("open", "close"):
        return jsonify({"ok": False, "error": "state doit être 'open' ou 'close'"}), 400
    result = _actuator_sim.set_roof(state)
    return jsonify(result)


@_emulator_app.get("/api/health")
def health():
    """Heartbeat de l'émulateur."""
    return jsonify({
        "status": "ok",
        "uptime_s": int(time.time() - _start_time),
        "simulated": True,
        "wifi_rssi": -65,
        "firmware_version": "simulator-1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Endpoints d'administration (simulation uniquement)
# ---------------------------------------------------------------------------

@_emulator_app.post("/admin/inject_failure")
def inject_failure():
    """Active des scénarios de panne pour les tests."""
    body = request.get_json(silent=True) or {}
    if "offline_sensors" in body:
        _sensor_sim.set_offline_sensors(set(body["offline_sensors"]))
    if "stuck_valve" in body:
        _actuator_sim.inject_stuck_valve(body["stuck_valve"])
    if "wifi_loss" in body:
        _actuator_sim.inject_wifi_loss(bool(body["wifi_loss"]))
    if "dry_zone" in body:
        zone = int(body["dry_zone"])
        if zone in range(1, 5):
            _sensor_sim._moisture[zone] = 18.0
    if "weather_profile" in body:
        _sensor_sim.set_weather_profile(body["weather_profile"])
        _weather_sim.set_profile(body["weather_profile"])
    return jsonify({"ok": True, "message": "Pannes injectées"})


@_emulator_app.post("/admin/reset")
def admin_reset():
    """Réinitialise l'état de la simulation."""
    _actuator_sim.reset()
    return jsonify({"ok": True, "message": "Simulation réinitialisée"})


@_emulator_app.get("/admin/state")
def admin_state():
    """Dump complet de l'état de simulation."""
    _sensor_sim.tick()
    snap = _sensor_sim.snapshot()
    return jsonify({
        "sensor_snapshot": snap,
        "actuator_status": _actuator_sim.get_all_status(),
        "weather": _weather_sim.get_current_conditions(),
        "uptime_s": int(time.time() - _start_time),
    })


@_emulator_app.get("/admin/weather/profiles")
def weather_profiles():
    return jsonify(WeatherSimulator.list_profiles())


# ---------------------------------------------------------------------------
# Point d'entrée pour le thread daemon
# ---------------------------------------------------------------------------

def start_emulator(host: str = "127.0.0.1", port: int = 8081,
                   speed: float = 1.0, weather_profile: str = "printemps_normal") -> None:
    """Démarre l'émulateur. Appelé dans un thread daemon depuis run.py."""
    _init_simulators(speed=speed, weather_profile=weather_profile)
    log.info("Émulateur Arduino démarré sur http://%s:%d", host, port)
    _emulator_app.run(host=host, port=port, use_reloader=False, debug=False)


def get_weather_sim() -> WeatherSimulator:
    """Accès au simulateur météo depuis l'app principale."""
    return _weather_sim
