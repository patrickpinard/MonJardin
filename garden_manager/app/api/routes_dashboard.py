"""Routes HTML — pages web du dashboard. plant_info passé à zone_detail."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, current_app, render_template, send_from_directory, \
    request, session, redirect

from ..models import Zone, SensorReading, JournalEntry, Planting, IrrigationLog, RoofLog, AdminUser, AlertRecipient, ALERT_TYPES

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
    plants_db = _load_plants_db()
    emoji_map      = {p["name"]: p.get("emoji", "🌱") for p in plants_db}
    water_need_map = {p["name"]: p.get("water_need", "medium") for p in plants_db}

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
            if not getattr(p, "water_need", None):
                p.water_need = water_need_map.get(p.vegetable_name, "medium")
        alert_since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
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
            "last_irrigation": None,  # rempli ci-dessous
        })

    # P4 : dernier arrosage par zone
    for zd in zones_data:
        zd["last_irrigation"] = (IrrigationLog.query
                                 .filter_by(zone_id=zd["zone"].zone_id, action="open")
                                 .order_by(IrrigationLog.timestamp.desc())
                                 .first())

    # Bandeau d'alerte : zones dont l'humidité est sous le seuil bas
    alerting_zones = [zd for zd in zones_data if zd["mc"] == "low"]

    # Tri : zones sèches d'abord (mc=low), puis ok, puis high — par humidité croissante
    _mc_order = {"low": 0, "ok": 1, "high": 2}
    zones_data.sort(key=lambda zd: (_mc_order.get(zd["mc"], 1), zd["moisture"]))

    temp = sensor_data.get("temperature_c", 15.0) if sensor_data else 15.0
    temp_serre = sensor_data.get("temp_serre_c") if sensor_data else None

    # Prochaines récoltes globales (60 jours)
    from datetime import date
    today = date.today()
    all_plantings = Planting.query.filter_by(status="active").all()
    zone_name_map = {z.zone_id: z.name for z in zones}
    harvest_list = []
    for p in all_plantings:
        if p.expected_harvest_date:
            days_left = (p.expected_harvest_date - today).days
            if days_left <= 60:
                harvest_list.append({
                    "vegetable_name": p.vegetable_name,
                    "variety": p.variety or "",
                    "zone_id": p.zone_id,
                    "zone_name": zone_name_map.get(p.zone_id, f"Zone {p.zone_id}"),
                    "expected_harvest_date": p.expected_harvest_date,
                    "days_left": days_left,
                    "emoji": emoji_map.get(p.vegetable_name, "🌱"),
                })
    harvest_list.sort(key=lambda x: x["days_left"])

    return render_template(
        "dashboard.html",
        zones_data=zones_data,
        temperature_c=round(temp, 1),
        temp_serre_c=round(temp_serre, 1) if temp_serre is not None else None,
        roof_state=actuator_status.get("roof_state", "close"),
        weather=weather,
        recent_entries=recent_entries,
        arduino_reachable=sensor_data is not None,
        harvest_list=harvest_list,
        today_date=today,
        alerting_zones=alerting_zones,
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
    two_hours_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
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

    # Plant DB index for spacing, depth, tips, companions
    plants_db = _load_plants_db()
    plant_info = {v["name"]: v for v in plants_db}

    # Seasonal advice for current month
    current_month = date.today().month
    seasonal_plants = [
        v for v in plants_db
        if current_month in v.get("planting_months_ch", [])
        and (zone.has_roof or not v.get("greenhouse_recommended", False))
    ]
    seasonal_plants.sort(key=lambda v: v.get("difficulty", "medium"))

    # Group active plantings by species for the visual layout
    from collections import defaultdict
    zone_length = getattr(zone, "length_m", None) or 2.0
    zone_width  = getattr(zone, "width_m",  None) or 1.0
    species_map: dict = defaultdict(list)
    for p in plantings:
        if p.status == "active":
            species_map[p.vegetable_name].append(p)

    plant_species_summary = []
    used_area_cm2 = 0.0
    for vname, plist in species_map.items():
        info  = plant_info.get(vname, {})
        space = info.get("space_cm", 30)
        # Inter-rang : pour les semis en ligne (carotte, radis, oignon...).
        # Si absent, on retombe sur space_cm (grille carrée pour plants individuels).
        space_row = info.get("space_row_cm", space)
        count = len(plist)
        cols_fit = max(1, int(zone_length * 100 / space))
        rows_fit = max(1, int(zone_width  * 100 / space_row))
        capacity = cols_fit * rows_fit
        used_area_cm2 += space * space_row * count
        plant_species_summary.append({
            "name":      vname,
            "count":     count,
            "emoji":     info.get("emoji", "🌱"),
            "space_cm":  space,
            "space_row_cm": space_row,
            "color":     info.get("color_primary", "#4CAF50"),
            "water_need": info.get("water_need", "medium"),
            "capacity":  capacity,
        })

    total_area_cm2 = zone_length * 100 * zone_width * 100
    remaining_area_m2 = round(max(0.0, total_area_cm2 - used_area_cm2) / 10_000, 2)
    zone_occupancy_pct = min(100, round(used_area_cm2 / total_area_cm2 * 100)) if total_area_cm2 else 0

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
        plant_info=plant_info,
        seasonal_plants=seasonal_plants[:8],
        current_month=current_month,
        plant_species_summary=plant_species_summary,
        remaining_area_m2=remaining_area_m2,
        zone_occupancy_pct=zone_occupancy_pct,
    )


# Note : la page /zones (zones_overview) a été fusionnée avec /dashboard en v2.0


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
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=period_hours)

    MAX_EVENTS = 500
    irrigation_logs = (IrrigationLog.query
                       .filter(IrrigationLog.timestamp >= since)
                       .order_by(IrrigationLog.timestamp.desc())
                       .limit(MAX_EVENTS).all())
    roof_logs = (RoofLog.query
                 .filter(RoofLog.timestamp >= since)
                 .order_by(RoofLog.timestamp.desc())
                 .limit(MAX_EVENTS).all())
    journal_entries = (JournalEntry.query
                       .filter(JournalEntry.timestamp >= since)
                       .order_by(JournalEntry.timestamp.desc())
                       .limit(MAX_EVENTS).all())

    # Liste unifiée triée par timestamp desc
    events = []
    for e in irrigation_logs:
        events.append(dict(kind="irrigation", ts=e.timestamp,
                           action=e.action, trigger=e.trigger_type,
                           reason=e.reason, zone_id=e.zone_id,
                           moisture=e.moisture_at_trigger, level=None))
    for e in roof_logs:
        events.append(dict(kind="roof", ts=e.timestamp,
                           action=e.action, trigger=e.trigger_type,
                           reason=e.reason, zone_id=None,
                           moisture=None, level=None))
    for e in journal_entries:
        ttype = ("alert" if e.level in ("danger", "error", "warning") else "system")
        events.append(dict(kind="system", ts=e.timestamp,
                           action=None, trigger=ttype,
                           reason=e.message, zone_id=None,
                           moisture=None, level=e.level))
    events.sort(key=lambda x: x["ts"], reverse=True)
    events = events[:MAX_EVENTS]

    return render_template("journal.html", events=events, period=period,
                           zones_count=len(set(e["zone_id"] for e in events if e["zone_id"])))


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


@dashboard_bp.post("/settings/sim_profile")
def settings_sim_profile():
    """Sauvegarde le profil météo dans .env ET l'applique à l'émulateur en live."""
    import requests as _req
    from flask import jsonify as _json

    VALID_PROFILES = {
        "printemps_normal", "ete_chaud", "ete_orageux",
        "automne_humide", "gel_tardif", "canicule",
    }
    if request.is_json:
        profile = (request.get_json(silent=True) or {}).get("profile", "")
    else:
        profile = request.form.get("profile", "")
    if not isinstance(profile, str) or profile not in VALID_PROFILES:
        return _json({"ok": False, "error": "Profil inconnu"}), 400

    # 1. Persistance dans .env
    _update_env_var("WEATHER_PROFILE", profile)
    current_app.config["WEATHER_PROFILE"] = profile

    # 2. Application immédiate à l'émulateur (in-memory)
    emulator_url = f"http://127.0.0.1:{current_app.config.get('EMULATOR_PORT', 8081)}/admin/inject_failure"
    try:
        _req.post(emulator_url, json={"weather_profile": profile}, timeout=2)
    except Exception as e:
        log.warning("Impossible de notifier l'émulateur pour le profil : %s", e)

    # 3. Mettre à jour le WeatherService si possible
    ws = current_app.extensions.get("weather_service")
    if ws and hasattr(ws, "_sim") and ws._sim is not None:
        try:
            ws._sim.set_profile(profile)
        except Exception:
            pass

    return _json({"ok": True, "profile": profile})


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
        user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
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
    from ..models import db as _db, SensorReading
    import os
    users             = AdminUser.query.order_by(AdminUser.created_at).all()
    alert_recipients  = AlertRecipient.query.order_by(AlertRecipient.created_at).all()
    smtp_user         = current_app.config.get("SMTP_USER", "")
    smtp_configured   = bool(smtp_user and current_app.config.get("SMTP_PASSWORD", ""))
    db_path           = current_app.config.get("SQLALCHEMY_DATABASE_URI", "").replace("sqlite:///", "")
    try:
        db_size_kb = round(os.path.getsize(db_path) / 1024)
    except Exception:
        db_size_kb = None
    total_readings = SensorReading.query.count()
    weather    = current_app.extensions["weather_service"].get_current()
    sim_speed  = int(current_app.config.get("SIMULATION_SPEED", 1))
    sim_profiles = [
        {"id": "printemps_normal", "label": "🌸 Printemps normal"},
        {"id": "ete_chaud",        "label": "☀️ Été chaud"},
        {"id": "ete_orageux",      "label": "⛈ Été orageux"},
        {"id": "automne_humide",   "label": "🍂 Automne humide"},
        {"id": "gel_tardif",       "label": "❄️ Gel tardif (Saints de Glace)"},
        {"id": "canicule",         "label": "🔥 Canicule"},
    ]
    return render_template(
        "admin.html",
        users=users,
        alert_recipients=alert_recipients,
        alert_types_config=ALERT_TYPES,
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
        weather=weather,
        sim_speed=sim_speed,
        sim_profiles=sim_profiles,
        current_weather_profile=current_app.config.get("WEATHER_PROFILE", "printemps_normal"),
    )


import re as _re
_EMAIL_RE = _re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

@dashboard_bp.post("/admin/alerts/add")
def admin_add_alert():
    from ..models import db as _db
    email = request.form.get("email", "").strip().lower()
    name  = request.form.get("name", "").strip()
    types = request.form.getlist("alert_types")
    # M14 : validation email par regex (pas seulement présence de "@")
    if not email or not _EMAIL_RE.match(email):
        return redirect("/admin?tab=alertes&error=invalid_email")
    if AlertRecipient.query.filter_by(email=email).first():
        return redirect("/admin?tab=alertes&error=email_exists")
    r = AlertRecipient(email=email, name=name or None)
    r.alert_types = types if types else [a["id"] for a in ALERT_TYPES]
    _db.session.add(r)
    _db.session.commit()
    return redirect("/admin?tab=alertes")


@dashboard_bp.post("/admin/alerts/<int:rid>/toggle")
def admin_toggle_alert(rid: int):
    from ..models import db as _db
    r = AlertRecipient.query.get_or_404(rid)
    r.enabled = not r.enabled
    _db.session.commit()
    return redirect("/admin?tab=alertes")


@dashboard_bp.post("/admin/alerts/<int:rid>/edit")
def admin_edit_alert(rid: int):
    from ..models import db as _db
    r     = AlertRecipient.query.get_or_404(rid)
    email = request.form.get("email", "").strip().lower()
    name  = request.form.get("name", "").strip()
    types = request.form.getlist("alert_types")
    if email and _EMAIL_RE.match(email):
        existing = AlertRecipient.query.filter_by(email=email).first()
        if not existing or existing.id == rid:
            r.email = email
    r.name        = name or None
    r.alert_types = types
    _db.session.commit()
    return redirect("/admin?tab=alertes")


@dashboard_bp.post("/admin/alerts/<int:rid>/delete")
def admin_delete_alert(rid: int):
    from ..models import db as _db
    r = AlertRecipient.query.get_or_404(rid)
    _db.session.delete(r)
    _db.session.commit()
    return redirect("/admin?tab=alertes")


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
