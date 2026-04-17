"""Routes HTML — pages web du dashboard."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, current_app, render_template

from ..models import Zone, SensorReading, JournalEntry, Planting, IrrigationLog, RoofLog

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    return dashboard()


@dashboard_bp.get("/dashboard")
def dashboard():
    arduino = current_app.extensions["arduino_client"]
    sensor_data = arduino.get_all_sensors()
    actuator_status = arduino.get_actuator_status() or {"valves": [], "roof_state": "close"}
    weather = current_app.extensions["weather_service"].get_current()
    recent_entries = (JournalEntry.query
                      .order_by(JournalEntry.timestamp.desc())
                      .limit(10).all())
    zones = Zone.query.order_by(Zone.zone_id).all()

    # Construire les données de zones pour le template
    zones_map = {}
    if sensor_data:
        for z in sensor_data.get("zones", []):
            zones_map[z["zone_id"]] = z

    valve_map = {v["zone_id"]: v["state"] for v in actuator_status.get("valves", [])}

    zones_data = []
    for zone in zones:
        z_sensor = zones_map.get(zone.zone_id, {})
        if not z_sensor:
            last = (SensorReading.query.filter_by(zone_id=zone.zone_id)
                    .order_by(SensorReading.timestamp.desc()).first())
            moisture = last.soil_moisture_pct if last else 50.0
        else:
            moisture = z_sensor.get("soil_moisture_pct", 50.0)

        # Classe CSS selon humidité
        if moisture < 30:
            moisture_class = "moisture-low"
        elif moisture > 65:
            moisture_class = "moisture-high"
        else:
            moisture_class = "moisture-ok"

        plantings = Planting.query.filter_by(zone_id=zone.zone_id, status="active").all()
        zones_data.append({
            "zone": zone,
            "moisture": round(moisture, 1),
            "moisture_class": moisture_class,
            "valve_state": valve_map.get(zone.zone_id, "close"),
            "plantings": plantings,
        })

    temp = sensor_data.get("temperature_c", 15.0) if sensor_data else 15.0
    temp_serre = sensor_data.get("temp_serre_c") if sensor_data else None
    return render_template(
        "dashboard.html",
        zones_data=zones_data,
        temperature_c=round(temp, 1),
        temp_serre_c=round(temp_serre, 1) if temp_serre is not None else None,
        roof_state=actuator_status.get("roof_state", "close"),
        weather=weather,
        recent_entries=recent_entries,
        arduino_reachable=sensor_data is not None,
    )


@dashboard_bp.get("/zones/<int:zone_id>")
def zone_detail(zone_id: int):
    zone = Zone.query.get_or_404(zone_id)
    advisor = current_app.extensions["planting_advisor"]
    plantings = Planting.query.filter_by(zone_id=zone_id).order_by(Planting.planted_date.desc()).all()
    compatibility_warnings = advisor.check_zone_compatibility(zone_id)
    harvest_forecast = advisor.get_harvest_forecast(zone_id)
    return render_template(
        "zone_detail.html",
        zone=zone,
        plantings=plantings,
        compatibility_warnings=compatibility_warnings,
        harvest_forecast=harvest_forecast,
    )


@dashboard_bp.get("/zones")
def zones_overview():
    arduino = current_app.extensions["arduino_client"]
    sensor_data = arduino.get_all_sensors()
    actuator_status = arduino.get_actuator_status() or {"valves": [], "roof_state": "close"}
    weather = current_app.extensions["weather_service"].get_current()

    zones = Zone.query.order_by(Zone.zone_id).all()
    plants_db = _load_plants_db()
    emoji_map = {p["name"]: p.get("emoji", "🌱") for p in plants_db}
    color_map = {p["name"]: p.get("color_primary", "") for p in plants_db}

    zones_map = {}
    if sensor_data:
        for z in sensor_data.get("zones", []):
            zones_map[z["zone_id"]] = z

    valve_map = {v["zone_id"]: v["state"] for v in actuator_status.get("valves", [])}

    zones_data = []
    for zone in zones:
        z_sensor = zones_map.get(zone.zone_id, {})
        if not z_sensor:
            last = (SensorReading.query.filter_by(zone_id=zone.zone_id)
                    .order_by(SensorReading.timestamp.desc()).first())
            moisture = last.soil_moisture_pct if last else 50.0
        else:
            moisture = z_sensor.get("soil_moisture_pct", 50.0)

        mc = ("low" if moisture < zone.moisture_threshold_low
              else "high" if moisture > zone.moisture_threshold_high else "ok")

        plantings = Planting.query.filter_by(zone_id=zone.zone_id, status="active").all()
        for p in plantings:
            p.emoji = emoji_map.get(p.vegetable_name, "🌱")
            p.color = color_map.get(p.vegetable_name, "")

        zones_data.append({
            "zone": zone,
            "moisture": round(moisture, 1),
            "mc": mc,
            "valve_state": valve_map.get(zone.zone_id, "close"),
            "plantings": plantings,
        })

    temp_ext = sensor_data.get("temperature_c") if sensor_data else None
    temp_serre = sensor_data.get("temp_serre_c") if sensor_data else None
    return render_template(
        "zones_overview.html",
        zones_data=zones_data,
        temp_ext=round(temp_ext, 1) if temp_ext is not None else weather.get("temperature"),
        temp_serre=round(temp_serre, 1) if temp_serre is not None else None,
        roof_state=actuator_status.get("roof_state", "close"),
    )


@dashboard_bp.get("/history")
def history():
    return render_template("history.html")


@dashboard_bp.get("/journal")
def journal_page():
    limit = 500
    irrigation_logs = (IrrigationLog.query
                       .order_by(IrrigationLog.timestamp.desc())
                       .limit(limit).all())
    roof_logs = (RoofLog.query
                 .order_by(RoofLog.timestamp.desc())
                 .limit(limit).all())
    journal_entries = (JournalEntry.query
                       .order_by(JournalEntry.timestamp.desc())
                       .limit(limit).all())
    return render_template(
        "journal.html",
        irrigation_logs=irrigation_logs,
        roof_logs=roof_logs,
        journal_entries=journal_entries,
    )


def _load_plants_db() -> list:
    db_path = current_app.config.get("PLANTS_DB_PATH",
        Path(__file__).parent.parent.parent / "data" / "plants_database.json")
    try:
        with open(db_path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("plants", data.get("vegetables", []))
    except (FileNotFoundError, ValueError):
        return []


@dashboard_bp.get("/plants")
def plants():
    plants_list = _load_plants_db()
    return render_template("plants.html", plants=plants_list)


@dashboard_bp.get("/plants/<name>")
def plant_detail(name: str):
    plants_list = _load_plants_db()
    plant = next((p for p in plants_list if p["name"].lower() == name.lower()), None)
    if plant is None:
        from flask import abort
        abort(404)
    zones = Zone.query.order_by(Zone.zone_id).all()
    today = datetime.today().strftime("%Y-%m-%d")
    days = plant.get("days_to_harvest", 90)
    harvest_default = (datetime.today() + timedelta(days=days)).strftime("%Y-%m-%d")
    return render_template(
        "plant_detail.html",
        plant=plant,
        zones=zones,
        today=today,
        harvest_date_default=harvest_default,
    )


@dashboard_bp.get("/system/arduino")
def arduino_control():
    return render_template("arduino_control.html")


@dashboard_bp.get("/system/raspberry")
def raspberry_pi():
    return render_template("raspberry_pi.html")


@dashboard_bp.get("/settings")
def settings():
    zones = Zone.query.order_by(Zone.zone_id).all()
    sim_mode = current_app.config.get("SIMULATION_MODE", False)
    weather = current_app.extensions["weather_service"].get_current()
    from simulator.weather_simulator import WeatherSimulator
    profiles = WeatherSimulator.list_profiles() if sim_mode else []
    return render_template(
        "settings.html",
        zones=zones,
        weather=weather,
        sim_profiles=profiles,
    )
