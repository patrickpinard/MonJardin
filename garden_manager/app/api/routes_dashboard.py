"""Routes HTML — pages web du dashboard."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, current_app, render_template, send_from_directory, \
    request, session, redirect

from ..models import Zone, SensorReading, JournalEntry, Planting, IrrigationLog, RoofLog, AdminUser

dashboard_bp = Blueprint("dashboard", __name__)
log = logging.getLogger(__name__)


@dashboard_bp.get("/sw.js")
def service_worker():
    return send_from_directory(
        Path(__file__).parent.parent / "static", "sw.js",
        mimetype="application/javascript"
    )

@dashboard_bp.get("/manifest.json")
def manifest():
    return send_from_directory(
        Path(__file__).parent.parent / "static", "manifest.json",
        mimetype="application/manifest+json"
    )

@dashboard_bp.get("/")
def index():
    return dashboard()


@dashboard_bp.get("/dashboard")
def dashboard():
    arduino = current_app.extensions["arduino_client"]
    sensor_data = arduino.get_all_sensors()
    actuator_status = arduino.get_actuator_status() or {"valves": [], "roof_state": "close"}
    weather = current_app.extensions["weather_service"].get_current()
    try:
        recent_entries = (JournalEntry.query
                          .order_by(JournalEntry.timestamp.desc())
                          .limit(10).all())
    except Exception as e:
        log.warning("Dashboard : échec lecture journal : %s", e)
        recent_entries = []
    try:
        zones = Zone.query.order_by(Zone.zone_id).all()
    except Exception as e:
        log.warning("Dashboard : échec lecture zones : %s", e)
        zones = []

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

        mc = ("low" if moisture < zone.moisture_threshold_low
              else "high" if moisture > zone.moisture_threshold_high else "ok")

        plantings = Planting.query.filter_by(zone_id=zone.zone_id, status="active").all()
        alert_since = datetime.utcnow() - timedelta(hours=2)
        recent = (SensorReading.query
                  .filter(SensorReading.zone_id == zone.zone_id,
                          SensorReading.timestamp >= alert_since)
                  .all())
        is_alerting = (len(recent) >= 3 and
                       all(r.soil_moisture_pct < zone.moisture_threshold_low for r in recent))
        zones_data.append({
            "zone": zone,
            "moisture": round(moisture, 1),
            "mc": mc,
            "valve_state": valve_map.get(zone.zone_id, "close"),
            "plantings": plantings,
            "is_alerting": is_alerting,
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
    from datetime import date
    zone = Zone.query.get_or_404(zone_id)
    advisor = current_app.extensions["planting_advisor"]
    plantings = Planting.query.filter_by(zone_id=zone_id).order_by(Planting.planted_date.desc()).all()
    compatibility_warnings = advisor.check_zone_compatibility(zone_id)
    harvest_forecast = advisor.get_harvest_forecast(zone_id, days=30)

    # Données live capteur
    arduino = current_app.extensions["arduino_client"]
    sensor_data = arduino.get_all_sensors()
    actuator_status = arduino.get_actuator_status() or {"valves": [], "roof_state": "close"}

    current_moisture = None
    current_temp = None
    if sensor_data:
        for z in sensor_data.get("zones", []):
            if z["zone_id"] == zone_id:
                current_moisture = round(z.get("soil_moisture_pct", 0), 1)
                break
        current_temp = sensor_data.get("temperature_c")

    if current_moisture is None:
        last = (SensorReading.query.filter_by(zone_id=zone_id)
                .order_by(SensorReading.timestamp.desc()).first())
        current_moisture = round(last.soil_moisture_pct, 1) if last else None
        if current_temp is None and last:
            current_temp = last.temperature_c

    valve_state = "close"
    for v in actuator_status.get("valves", []):
        if v.get("zone_id") == zone_id:
            valve_state = v.get("state", "close")
            break
    roof_state = actuator_status.get("roof_state", "close")

    # Moisture class
    if current_moisture is not None:
        if current_moisture < zone.moisture_threshold_low:
            mc = "low"
        elif current_moisture > zone.moisture_threshold_high:
            mc = "high"
        else:
            mc = "ok"
    else:
        mc = "ok"

    # Dernier arrosage
    last_irrigation = (IrrigationLog.query
                       .filter_by(zone_id=zone_id, action="open")
                       .order_by(IrrigationLog.timestamp.desc())
                       .first())

    # Événements récents de cette zone (journal)
    recent_events = (IrrigationLog.query
                     .filter_by(zone_id=zone_id)
                     .order_by(IrrigationLog.timestamp.desc())
                     .limit(8).all())

    # Tendance humidité (2 dernières heures)
    two_hours_ago = datetime.utcnow() - timedelta(hours=2)
    recent_readings = (SensorReading.query
                       .filter(SensorReading.zone_id == zone_id,
                               SensorReading.timestamp >= two_hours_ago)
                       .order_by(SensorReading.timestamp.asc()).all())
    trend = None
    if len(recent_readings) >= 4:
        first_half = [r.soil_moisture_pct for r in recent_readings[:len(recent_readings)//2]]
        second_half = [r.soil_moisture_pct for r in recent_readings[len(recent_readings)//2:]]
        diff = (sum(second_half)/len(second_half)) - (sum(first_half)/len(first_half))
        trend = "up" if diff > 1.5 else ("down" if diff < -1.5 else "stable")

    return render_template(
        "zone_detail.html",
        zone=zone,
        plantings=plantings,
        compatibility_warnings=compatibility_warnings,
        harvest_forecast=harvest_forecast,
        today_date=date.today(),
        current_moisture=current_moisture,
        current_temp=round(current_temp, 1) if current_temp else None,
        temp_serre_c=round(sensor_data.get("temp_serre_c"), 1) if sensor_data and sensor_data.get("temp_serre_c") else None,
        valve_state=valve_state,
        roof_state=roof_state,
        mc=mc,
        last_irrigation=last_irrigation,
        recent_events=recent_events,
        trend=trend,
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
        temperature_c=round(temp_ext, 1) if temp_ext is not None else weather.get("temperature"),
        temp_serre_c=round(temp_serre, 1) if temp_serre is not None else None,
        roof_state=actuator_status.get("roof_state", "close"),
    )


@dashboard_bp.get("/history")
def history():
    return render_template("history.html")


@dashboard_bp.get("/journal")
def journal_page():
    from flask import request as freq
    from datetime import date as _date, time as _time
    period = freq.args.get("period", "week")
    if period == "day":
        since = datetime.combine(_date.today(), _time.min)
    else:
        period_hours = {"week": 168, "month": 720, "year": 8760}.get(period, 168)
        since = datetime.utcnow() - timedelta(hours=period_hours)

    irrigation_logs = (IrrigationLog.query
                       .filter(IrrigationLog.timestamp >= since)
                       .order_by(IrrigationLog.timestamp.desc())
                       .all())
    roof_logs = (RoofLog.query
                 .filter(RoofLog.timestamp >= since)
                 .order_by(RoofLog.timestamp.desc())
                 .all())
    journal_entries = (JournalEntry.query
                       .filter(JournalEntry.timestamp >= since)
                       .order_by(JournalEntry.timestamp.desc())
                       .all())
    return render_template(
        "journal.html",
        irrigation_logs=irrigation_logs,
        roof_logs=roof_logs,
        journal_entries=journal_entries,
        period=period,
    )


def _load_plants_db() -> list:
    db_path = current_app.config.get("PLANTS_DB_PATH",
        Path(__file__).parent.parent.parent / "data" / "plants_database.json")
    try:
        with open(db_path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("plants", data.get("vegetables", []))
    except FileNotFoundError:
        log.warning("Base de données plantes introuvable : %s", db_path)
        return []
    except ValueError as e:
        log.warning("Erreur parsing plants_database.json : %s", e)
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


@dashboard_bp.post("/settings/garden")
def settings_garden():
    name     = request.form.get("garden_name", "MonJardin").strip()
    location = request.form.get("garden_location", "Vullierens, Vaud").strip()
    owner    = request.form.get("garden_owner", "").strip()
    _update_env_var("GARDEN_NAME", name)
    _update_env_var("GARDEN_LOCATION", location)
    _update_env_var("GARDEN_OWNER", owner)
    current_app.config["GARDEN_NAME"]     = name
    current_app.config["GARDEN_LOCATION"] = location
    current_app.config["GARDEN_OWNER"]    = owner
    return redirect("/settings")


@dashboard_bp.post("/settings/sim_speed")
def settings_sim_speed():
    allowed = {1, 5, 10, 20, 50, 100}
    try:
        speed = int(request.form.get("speed", 1))
    except (ValueError, TypeError):
        speed = 1
    if speed not in allowed:
        speed = 1
    _update_env_var("SIMULATION_SPEED", str(speed))
    current_app.config["SIMULATION_SPEED"] = speed
    scheduler = current_app.extensions.get("scheduler")
    if scheduler:
        base_interval = current_app.config.get("AUTOMATION_INTERVAL", 60)
        cycle_interval = max(5, int(base_interval / speed))
        weather_interval = max(30, int(1800 / speed))
        scheduler.reschedule_job("automation_cycle", trigger="interval", seconds=cycle_interval)
        scheduler.reschedule_job("weather_poll", trigger="interval", seconds=weather_interval)
    return redirect("/settings")


def _update_env_var(key: str, value: str):
    """Mise à jour d'une variable dans le fichier .env sans perdre les autres."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    found = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# ── Login / Logout ────────────────────────────────────────────────────────────

@dashboard_bp.get("/login")
def login_page():
    if "auth_user" in session:
        return redirect("/dashboard")
    next_url = request.args.get("next", "/dashboard")
    return render_template("login.html", next_url=next_url)


@dashboard_bp.post("/login/post")
def login_post():
    username = request.form.get("username", "").strip()
    pin      = request.form.get("pin", "").strip()
    next_url = request.form.get("next_url", "/dashboard")
    user = AdminUser.query.filter_by(username=username, enabled=True).first()
    if user and user.check_pin(pin):
        from datetime import datetime
        user.last_login = datetime.utcnow()
        from ..models import db
        db.session.commit()
        session["auth_user"] = username
        session.permanent = True
        return redirect(next_url)
    return render_template("login.html", next_url=next_url, error="Identifiant ou PIN incorrect.")


@dashboard_bp.get("/logout")
def logout():
    session.pop("auth_user", None)
    return redirect("/login")


# ── Administration ────────────────────────────────────────────────────────────

@dashboard_bp.get("/admin")
def admin_page():
    users = AdminUser.query.order_by(AdminUser.created_at).all()
    smtp_user       = current_app.config.get("SMTP_USER", "")
    smtp_configured = bool(smtp_user and current_app.config.get("SMTP_PASSWORD", ""))
    from ..models import db, SensorReading
    import os
    db_path = current_app.config.get("SQLALCHEMY_DATABASE_URI", "").replace("sqlite:///", "")
    try:
        db_size_kb = round(os.path.getsize(db_path) / 1024)
    except Exception:
        db_size_kb = None
    total_readings = SensorReading.query.count()
    return render_template(
        "admin.html",
        users=users,
        smtp_host=current_app.config.get("SMTP_HOST", ""),
        smtp_port=current_app.config.get("SMTP_PORT", 587),
        smtp_user=smtp_user,
        mail_sender=current_app.config.get("MAIL_DEFAULT_SENDER", smtp_user),
        mail_dest=current_app.config.get("ADMIN_NOTIFICATION_EMAIL", ""),
        mail_tls=current_app.config.get("MAIL_USE_TLS", True),
        smtp_configured=smtp_configured,
        db_size_kb=db_size_kb,
        total_readings=total_readings,
        simulation_mode=current_app.config.get("SIMULATION_MODE", False),
        current_user=session.get("auth_user"),
    )


@dashboard_bp.post("/admin/users/add")
def admin_add_user():
    from ..models import db, AdminUser
    username = request.form.get("username", "").strip()
    pin      = request.form.get("pin", "").strip()
    if not username or not pin or len(pin) < 4:
        return redirect("/admin?error=invalid")
    if AdminUser.query.filter_by(username=username).first():
        return redirect("/admin?error=exists")
    db.session.add(AdminUser(username=username, pin_hash=AdminUser.hash_pin(pin)))
    db.session.commit()
    return redirect("/admin")


@dashboard_bp.post("/admin/users/<int:uid>/toggle")
def admin_toggle_user(uid):
    from ..models import db, AdminUser
    user = AdminUser.query.get_or_404(uid)
    user.enabled = not user.enabled
    db.session.commit()
    return redirect("/admin")


@dashboard_bp.post("/admin/users/<int:uid>/pin")
def admin_change_pin(uid):
    from ..models import db, AdminUser
    user = AdminUser.query.get_or_404(uid)
    new_pin = request.form.get("pin", "").strip()
    if len(new_pin) >= 4:
        user.pin_hash = AdminUser.hash_pin(new_pin)
        db.session.commit()
    return redirect("/admin")


@dashboard_bp.post("/admin/users/<int:uid>/delete")
def admin_delete_user(uid):
    from ..models import db, AdminUser
    user = AdminUser.query.get_or_404(uid)
    db.session.delete(user)
    db.session.commit()
    return redirect("/admin")


@dashboard_bp.get("/conseils")
def conseils():
    return render_template("conseils.html")


@dashboard_bp.get("/about")
def about_page():
    return render_template("about.html")
