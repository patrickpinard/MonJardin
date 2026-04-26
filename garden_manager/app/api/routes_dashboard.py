"""Routes HTML — pages web du dashboard. plant_info passé à zone_detail."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

from flask import Blueprint, current_app, render_template, send_from_directory, \
    request, session, redirect, flash, url_for

from ..models import Zone, SensorReading, JournalEntry, Planting, IrrigationLog, RoofLog, AdminUser, AlertRecipient, ALERT_TYPES, db

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
        zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
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

    # ── species_summary par zone groupé par (espèce + variété) ──
    _plants_db = _load_plants_db()
    _emoji_global = {p["name"]: p.get("emoji", "🌱") for p in _plants_db}
    from collections import defaultdict as _dd
    for zd in zones_data:
        groups: dict = _dd(list)
        for p in zd["plantings"]:
            key = (p.vegetable_name, (p.variety or "").strip())
            groups[key].append(p)
        species = []
        for (vname, variety), plist in groups.items():
            rep = max(plist, key=lambda p: p.id)
            harvest_dates = [p.expected_harvest_date for p in plist if p.expected_harvest_date]
            next_harvest  = min(harvest_dates) if harvest_dates else None
            d_left = (next_harvest - date.today()).days if next_harvest else None
            species.append({
                "name":       vname,
                "variety":    variety,
                "display_name": f"{vname} · {variety}" if variety else vname,
                "emoji":      _emoji_global.get(vname, "🌱"),
                "count":      len(plist),
                "rep_id":     rep.id,
                "days_left":  d_left,
            })
        # Trier : récolte proche en premier
        species.sort(key=lambda s: (s["days_left"] is None, s["days_left"] or 9999))
        zd["species_summary"] = species

    # Bandeau d'alerte : zones dont l'humidité est sous le seuil bas
    alerting_zones = [zd for zd in zones_data if zd["mc"] == "low"]

    # Tri : zones sèches d'abord (mc=low), puis ok, puis high — par humidité croissante
    _mc_order = {"low": 0, "ok": 1, "high": 2}
    zones_data.sort(key=lambda zd: (_mc_order.get(zd["mc"], 1), zd["moisture"]))

    temp = sensor_data.get("temperature_c", 15.0) if sensor_data else 15.0
    temp_serre = sensor_data.get("temp_serre_c") if sensor_data else None

    # Prochaines récoltes globales (60 jours)
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

    # ── Calendrier de tâches saisonnier (mois courant) ─────
    advisor = current_app.extensions["planting_advisor"]
    current_month = today.month
    seasonal_vegs = advisor.get_seasonal_advice(current_month, limit=5)
    monthly_tasks = []
    # Tâches "à semer/planter ce mois"
    for v in seasonal_vegs:
        already_in = any(p.vegetable_name == v["name"] for p in all_plantings)
        monthly_tasks.append({
            "kind": "plant",
            "icon": v.get("emoji", "🌱"),
            "label": f"Planter / semer {v['name']}",
            "detail": f"Mois optimal en Suisse" + (" · déjà dans une zone" if already_in else ""),
            "done": already_in,
        })
    # Tâches "à récolter bientôt" (plantings active, récolte ≤ 14j)
    for p in all_plantings:
        if not p.expected_harvest_date:
            continue
        d_left = (p.expected_harvest_date - today).days
        if 0 <= d_left <= 14:
            monthly_tasks.append({
                "kind": "harvest",
                "icon": "🧺",
                "label": f"Récolter {p.vegetable_name}",
                "detail": (
                    "Prêt aujourd'hui !" if d_left == 0
                    else f"Dans {d_left} jour{'s' if d_left > 1 else ''}"
                ) + f" · {zone_name_map.get(p.zone_id, 'Zone ' + str(p.zone_id))}",
                "done": False,
            })
    # Limiter à 8 tâches max pour ne pas surcharger
    monthly_tasks = monthly_tasks[:8]
    MONTH_NAMES_FR = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                      "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    current_month_name = MONTH_NAMES_FR[current_month]

    # ── Bandeau d'actions concrètes (à faire maintenant) ──
    actions = []
    # 1. Zones à arroser (sol sec + mode auto/manual + vanne fermée)
    for zd in zones_data:
        if zd["mc"] == "low" and zd["zone"].irrigation_mode != "disabled" and zd["valve_state"] == "close":
            actions.append({
                "kind": "water",
                "icon": "💧",
                "label": f"Arroser {zd['zone'].name}",
                "detail": f"Sol sec ({zd['moisture']}%)",
                "zone_id": zd["zone"].zone_id,
                "btn_label": "Arroser",
                "btn_action": f"setValve({zd['zone'].zone_id}, 'open')",
                "color": "red",
            })
    # 2. Lucarne ouverte depuis longtemps (>3h)
    if actuator_status.get("roof_state") == "open":
        last_open = (RoofLog.query
                     .filter_by(action="open")
                     .order_by(RoofLog.timestamp.desc())
                     .first())
        if last_open:
            hours_open = (datetime.now(timezone.utc).replace(tzinfo=None) - last_open.timestamp).total_seconds() / 3600
            if hours_open > 3:
                actions.append({
                    "kind": "roof",
                    "icon": "🪟",
                    "label": "Lucarne serre ouverte",
                    "detail": f"Depuis {int(hours_open)}h — pensez à fermer",
                    "zone_id": 1,
                    "btn_label": "Fermer",
                    "btn_action": "setRoof('close')",
                    "color": "orange",
                })
    # 3. Récoltes à faire dans les 3 prochains jours
    soon_harvest = [p for p in all_plantings
                    if p.expected_harvest_date and 0 <= (p.expected_harvest_date - today).days <= 3]
    if soon_harvest:
        from collections import defaultdict as _dd
        by_zone = _dd(list)
        for p in soon_harvest:
            by_zone[p.zone_id].append(p)
        for zid, plist in by_zone.items():
            zname = zone_name_map.get(zid, f"Zone {zid}")
            names = ", ".join(set(p.vegetable_name for p in plist))
            actions.append({
                "kind": "harvest",
                "icon": "🧺",
                "label": f"Récolte {zname}",
                "detail": f"{len(plist)} plant(s) prêt(s) : {names}",
                "zone_id": zid,
                "btn_label": "Voir",
                "btn_action": f"location.href='/zones/{zid}'",
                "color": "green",
            })

    # ── Hero "Aujourd'hui" : greeting + phrases contextuelles ──
    now_h = datetime.now().hour
    if   now_h < 6:  greeting = "Bonne soirée"
    elif now_h < 12: greeting = "Bonjour"
    elif now_h < 18: greeting = "Bel après-midi"
    else:            greeting = "Bonsoir"
    DAY_NAMES_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    today_label = f"{DAY_NAMES_FR[today.weekday()]} {today.day} {current_month_name.lower()}"

    hero_lines = []
    # Météo : si pluie ou risque gel
    try:
        precip_prob = weather.get("precip_prob_pct", 0) or 0
        precip_mm   = weather.get("precip_mm_6h", 0) or 0
        if weather.get("frost_risk"):
            hero_lines.append({"icon":"❄️", "text": "Risque de gel — vannes et lucarne fermées préventivement."})
        elif precip_mm > 5 or precip_prob > 70:
            hero_lines.append({"icon":"🌧", "text": f"Pluie prévue ({precip_prob:.0f}%) — pas besoin d'arroser aujourd'hui."})
        elif weather.get("temperature", 0) > 30:
            hero_lines.append({"icon":"🌡", "text": f"Forte chaleur ({weather['temperature']}°C) — arrosage en soirée recommandé."})
    except Exception:
        pass
    # Récoltes prêtes ce jour
    harvests_today = [h for h in harvest_list if h.get("days_left", 99) <= 1]
    if harvests_today:
        names = ", ".join(set(h["vegetable_name"] for h in harvests_today[:3]))
        hero_lines.append({"icon":"🧺", "text": f"À récolter : {names} ({len(harvests_today)} prêt(s))."})
    # Lucarne ouverte longtemps
    if actuator_status.get("roof_state") == "open":
        last_open_log = (RoofLog.query.filter_by(action="open")
                         .order_by(RoofLog.timestamp.desc()).first())
        if last_open_log:
            hours_open = (datetime.now(timezone.utc).replace(tzinfo=None) - last_open_log.timestamp).total_seconds() / 3600
            if hours_open > 4:
                hero_lines.append({"icon":"🪟", "text": f"Lucarne ouverte depuis {int(hours_open)}h — pense à la fermer ce soir."})
    # Sol sec
    if alerting_zones:
        zone_names = ", ".join(zd["zone"].name for zd in alerting_zones[:2])
        hero_lines.append({"icon":"💧", "text": f"Sol sec dans : {zone_names} — arrosage automatique au prochain cycle."})
    # Aucune alerte → message positif
    if not hero_lines:
        hero_lines.append({"icon":"✨", "text": "Tout va bien — ton jardin n'a besoin de rien aujourd'hui."})

    # ── Pulse Score : santé globale du jardin (0-100) ──────
    # 40% humidité dans seuils, 30% pas d'alerte, 20% plants en bonne santé,
    # 10% météo favorable
    pulse_components = {}
    # Humidité : % de zones dans les seuils (mc=ok)
    n_zones = len(zones_data) or 1
    n_ok    = sum(1 for zd in zones_data if zd["mc"] == "ok")
    pulse_components["moisture"] = round(n_ok / n_zones * 40)
    # Alertes : plein si zéro alerte
    pulse_components["alerts"] = 30 if not alerting_zones else max(0, 30 - 10 * len(alerting_zones))
    # Plants : pourcentage de plants sans retard de récolte
    n_plants = len(all_plantings) or 1
    n_late = sum(1 for p in all_plantings if p.expected_harvest_date and (p.expected_harvest_date - today).days < -7)
    pulse_components["plants"] = round(max(0, (n_plants - n_late) / n_plants) * 20)
    # Météo : pleine si pas de gel, canicule, ni vent fort
    weather_score = 10
    if weather.get("frost_risk"): weather_score -= 5
    if (weather.get("temperature") or 0) > 32: weather_score -= 3
    if (weather.get("wind_kmh") or 0) > 40: weather_score -= 2
    pulse_components["weather"] = max(0, weather_score)
    pulse_score = sum(pulse_components.values())
    if   pulse_score >= 85: pulse_label, pulse_color = "Excellent", "green"
    elif pulse_score >= 65: pulse_label, pulse_color = "Bon",       "green"
    elif pulse_score >= 45: pulse_label, pulse_color = "Moyen",     "orange"
    else:                   pulse_label, pulse_color = "À surveiller", "red"

    # ── Forecast 24h structuré pour bandeau météo riche ────
    weather_service = current_app.extensions["weather_service"]
    forecast_24h = []
    forecast_by_day = []
    try:
        # 7 jours d'horaire pour pouvoir agréger jusqu'à une semaine
        full_forecast = weather_service.get_forecast_hourly(days=7) or []
        # Bandeau 24h pills (top dashboard)
        for f in full_forecast[:24]:
            ts = f.get("hour") or f.get("timestamp")
            if isinstance(ts, str):
                try:
                    dt_h = datetime.fromisoformat(ts.replace("Z","+00:00")).hour
                except Exception:
                    dt_h = 0
            else:
                dt_h = getattr(ts, "hour", 0)
            forecast_24h.append({
                "hour":        f"{dt_h:02d}h",
                "temperature": f.get("temperature"),
                "precip_pct":  int(f.get("precip_prob_pct", 0) or 0),
                "precip_mm":   round(f.get("precip_mm", 0) or 0, 1),
                "icon":        ("🌧" if (f.get("precip_mm", 0) or 0) > 0
                                else "🌦" if (f.get("precip_prob_pct", 0) or 0) > 40
                                else "☀️"),
            })

        # Forecast groupé par jour pour le tab Météo (48h → 2 jours)
        from collections import defaultdict as _dd
        days_buckets = _dd(list)
        for f in full_forecast:
            ts = f.get("hour") or f.get("timestamp")
            if isinstance(ts, str):
                try:
                    dt_obj = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    continue
            else:
                dt_obj = ts
            days_buckets[dt_obj.date()].append(f)

        for d, hours in sorted(days_buckets.items())[:7]:
            temps   = [h.get("temperature") for h in hours if h.get("temperature") is not None]
            precips = [h.get("precip_mm") or 0 for h in hours]
            probs   = [h.get("precip_prob_pct") or 0 for h in hours]
            t_min = min(temps) if temps else None
            t_max = max(temps) if temps else None
            precip_total = sum(precips)
            prob_max = max(probs) if probs else 0
            # Label jour
            if d == today:               label = "Aujourd'hui"
            elif d == today + timedelta(days=1): label = "Demain"
            else:                        label = DAY_NAMES_FR[d.weekday()].capitalize() + f" {d.day}"
            forecast_by_day.append({
                "label":   label,
                "date":    d.strftime("%d.%m"),
                "t_min":   round(t_min, 1) if t_min is not None else None,
                "t_max":   round(t_max, 1) if t_max is not None else None,
                "precip":  round(precip_total, 1),
                "prob_max": int(prob_max),
                "icon":    ("🌧" if precip_total > 2 else "🌦" if prob_max > 40 else "☀️"),
            })
    except Exception:
        pass

    # ── Détection précoce maladies / risques sanitaires ────
    disease_advisor = current_app.extensions.get("disease_advisor")
    disease_alerts = []
    if disease_advisor:
        try:
            full_forecast_for_disease = weather_service.get_forecast_48h() or []
            disease_alerts = disease_advisor.analyze(
                weather=weather,
                forecast_24h=full_forecast_for_disease[:24],
                active_plantings=all_plantings,
            )
        except Exception as e:
            log.warning("Disease advisor échec : %s", e)
            disease_alerts = []

    # Détection : configuration initiale faite ? Bannière masquée par l'utilisateur ?
    setup_done = _setup_done_path().exists()
    setup_skipped = _setup_skipped_path().exists()

    return render_template(
        "dashboard.html",
        zones_data=zones_data,
        setup_done=setup_done,
        setup_skipped=setup_skipped,
        temperature_c=round(temp, 1),
        temp_serre_c=round(temp_serre, 1) if temp_serre is not None else None,
        roof_state=actuator_status.get("roof_state", "close"),
        weather=weather,
        recent_entries=recent_entries,
        arduino_reachable=sensor_data is not None,
        harvest_list=harvest_list,
        today_date=today,
        alerting_zones=alerting_zones,
        actions=actions,
        monthly_tasks=monthly_tasks,
        current_month_name=current_month_name,
        # Hero
        hero_greeting=greeting,
        hero_today_label=today_label,
        hero_lines=hero_lines,
        # Pulse
        pulse_score=pulse_score,
        pulse_label=pulse_label,
        pulse_color=pulse_color,
        pulse_components=pulse_components,
        # Forecast
        forecast_24h=forecast_24h,
        forecast_by_day=forecast_by_day,
        # Détection maladies
        disease_alerts=disease_alerts,
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

    # ── Recommandation de plage horaire d'arrosage ───────────
    # Basée sur les water_need des plantations actives + la saison
    active_plantings = [p for p in plantings if p.status == "active"]
    water_needs = [plant_info.get(p.vegetable_name, {}).get("water_need", "medium")
                   for p in active_plantings]
    high_count = sum(1 for w in water_needs if w == "high")
    low_count  = sum(1 for w in water_needs if w == "low")
    month = date.today().month
    is_hot_season = month in (6, 7, 8)  # juin à août
    is_cold_season = month in (11, 12, 1, 2)  # novembre à février

    if not active_plantings:
        watering_window = {
            "label": "Soir (19h-21h)",
            "hours": "19:00–21:00",
            "reason": "Recommandation par défaut — limite l'évaporation.",
        }
    elif is_hot_season and high_count >= 1:
        watering_window = {
            "label": "Soir tard (20h-22h)",
            "hours": "20:00–22:00",
            "reason": f"{high_count} plant(s) gourmand(s) en eau en pleine saison chaude — arroser après le coucher du soleil pour éviter l'évaporation.",
        }
    elif is_hot_season:
        watering_window = {
            "label": "Soir (19h-21h)",
            "hours": "19:00–21:00",
            "reason": "Saison chaude — arrosage du soir pour limiter l'évaporation.",
        }
    elif is_cold_season:
        watering_window = {
            "label": "Matin (10h-12h)",
            "hours": "10:00–12:00",
            "reason": "Saison froide — arroser en milieu de matinée évite le gel des racines la nuit.",
        }
    elif low_count > len(active_plantings) / 2:
        watering_window = {
            "label": "Matin tôt (6h-9h)",
            "hours": "06:00–09:00",
            "reason": "Plants peu gourmands — un arrosage matinal léger suffit.",
        }
    else:
        watering_window = {
            "label": "Soir (19h-21h)",
            "hours": "19:00–21:00",
            "reason": "Mix de besoins — arrosage du soir, fenêtre la plus universelle.",
        }

    # Seasonal advice for current month
    current_month = date.today().month
    seasonal_plants = [
        v for v in plants_db
        if current_month in v.get("planting_months_ch", [])
        and (zone.has_roof or not v.get("greenhouse_recommended", False))
    ]
    seasonal_plants.sort(key=lambda v: v.get("difficulty", "medium"))

    # Group active plantings by (species, variety) — différencie ex. Tomate Cœur de bœuf vs Tomate Cerise
    from collections import defaultdict
    zone_length = getattr(zone, "length_m", None) or 2.0
    zone_width  = getattr(zone, "width_m",  None) or 1.0
    species_map: dict = defaultdict(list)
    for p in plantings:
        if p.status == "active":
            # Clé composite : (vegetable_name, variety|"")
            key = (p.vegetable_name, (p.variety or "").strip())
            species_map[key].append(p)

    # Tri des groupes par min(display_order) pour respecter l'ordre du drag & drop visuel
    sorted_groups = sorted(
        species_map.items(),
        key=lambda kv: (min((p.display_order or 0) for p in kv[1]), kv[0])
    )
    plant_species_summary = []
    used_area_cm2 = 0.0
    for (vname, variety), plist in sorted_groups:
        info  = plant_info.get(vname, {})
        space = info.get("space_cm", 30)
        # Inter-rang : pour les semis en ligne (carotte, radis, oignon...).
        space_row = info.get("space_row_cm", space)
        count = len(plist)
        cols_fit = max(1, int(zone_length * 100 / space))
        rows_fit = max(1, int(zone_width  * 100 / space_row))
        capacity = cols_fit * rows_fit
        used_area_cm2 += space * space_row * count

        # Représentant : la plantation la plus récente du groupe
        rep = max(plist, key=lambda p: p.id)
        harvest_dates = [p.expected_harvest_date for p in plist if p.expected_harvest_date]
        next_harvest  = min(harvest_dates) if harvest_dates else None
        days_left = (next_harvest - date.today()).days if next_harvest else None

        # Display label : "Tomate" ou "Tomate · Cœur de bœuf"
        display_name = f"{vname} · {variety}" if variety else vname

        plant_species_summary.append({
            "name":      vname,
            "variety":   variety,
            "display_name": display_name,
            "count":     count,
            "emoji":     info.get("emoji", "🌱"),
            "space_cm":  space,
            "space_row_cm": space_row,
            "color":     info.get("color_primary", "#4CAF50"),
            "water_need": info.get("water_need", "medium"),
            "capacity":  capacity,
            "rep_id":    rep.id,
            "harvest":   next_harvest.isoformat() if next_harvest else "",
            "days_left": days_left,
            "status":    rep.status,
            "notes":     rep.notes or "",
        })

    total_area_cm2 = zone_length * 100 * zone_width * 100
    remaining_area_m2 = round((total_area_cm2 - used_area_cm2) / 10_000, 2)
    # Pas de cap à 100% : si > 100, c'est une sur-occupation à signaler
    zone_occupancy_pct = round(used_area_cm2 / total_area_cm2 * 100) if total_area_cm2 else 0

    # ── Grille visuelle case-par-case ─────────────────────────────────
    # Chaque case = 30 cm × 30 cm. Chaque planting actif occupe ≥ 1 case.
    CELL_CM = 30
    grid_cols = max(4, int(zone_length * 100 / CELL_CM))
    grid_rows = max(2, int(zone_width  * 100 / CELL_CM))

    actives_for_grid = [p for p in plantings if p.status == "active"]
    # Construit la liste des cellules occupées + données pour le rendu
    grid_plantings = []
    occupied = set()  # set de (row, col)
    for p in actives_for_grid:
        info = plant_info.get(p.vegetable_name, {})
        r, c = (p.grid_row or 0), (p.grid_col or 0)
        w, h = max(1, p.grid_w or 1), max(1, p.grid_h or 1)
        # Clamp sur la grille
        r = max(0, min(r, grid_rows - 1))
        c = max(0, min(c, grid_cols - 1))
        if c + w > grid_cols: w = grid_cols - c
        if r + h > grid_rows: h = grid_rows - r
        for dr in range(h):
            for dc in range(w):
                occupied.add((r + dr, c + dc))
        days_left = ((p.expected_harvest_date - date.today()).days
                     if p.expected_harvest_date else None)
        grid_plantings.append({
            "id":            p.id,
            "row":           r,
            "col":           c,
            "w":             w,
            "h":             h,
            "name":          p.vegetable_name,
            "variety":       (p.variety or "").strip(),
            "display_name":  f"{p.vegetable_name} · {p.variety}" if p.variety else p.vegetable_name,
            "emoji":         info.get("emoji", "🌱"),
            "color":         info.get("color_primary", "#4CAF50"),
            "water_need":    p.water_need or info.get("water_need", "medium"),
            "harvest":       p.expected_harvest_date.isoformat() if p.expected_harvest_date else "",
            "days_left":     days_left,
            "status":        p.status,
            "notes":         p.notes or "",
            "is_seed":       (info.get("space_cm", 30) <= 10),  # carotte/radis/oignon = semis
        })
    # Liste des cases vides (pour drop targets)
    empty_cells = [(r, c) for r in range(grid_rows) for c in range(grid_cols)
                   if (r, c) not in occupied]

    # ── Photos de la zone groupées par mois puis par jour (vue calendrier) ──
    from .. models import ZonePhoto
    photos = (ZonePhoto.query
              .filter_by(zone_id=zone_id)
              .order_by(ZonePhoto.captured_at.desc())
              .all())
    photos_count = len(photos)
    # Group by month
    from collections import OrderedDict
    DAY_NAMES_FR_SHORT = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    MONTH_NAMES_FR = ["Janvier","Février","Mars","Avril","Mai","Juin",
                      "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
    by_month = OrderedDict()
    for ph in photos:
        d = ph.captured_at.date()
        month_key = (d.year, d.month)
        by_month.setdefault(month_key, OrderedDict())
        by_month[month_key].setdefault(d, []).append(ph)
    photos_by_month = []
    for (yr, mo), days in by_month.items():
        month_label = f"{MONTH_NAMES_FR[mo-1]} {yr}"
        days_list = []
        for d, plist in days.items():
            days_list.append({
                "day_num":  d.day,
                "day_name": DAY_NAMES_FR_SHORT[d.weekday()],
                "count":    len(plist),
                "photos":   [ph.to_dict() for ph in plist],
            })
        photos_by_month.append((month_label, days_list))

    # Liste de toutes les zones pour le sélecteur de l'onglet Graphiques
    all_zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()

    return render_template(
        "zone_detail.html",
        zone=zone,
        all_zones=all_zones,
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
        watering_window=watering_window,
        # Nouveau plan visuel case-par-case
        grid_cols=grid_cols,
        grid_rows=grid_rows,
        grid_plantings=grid_plantings,
        empty_cells=empty_cells,
        photos_count=photos_count,
        photos_by_month=photos_by_month,
    )


# Note : la page /zones (zones_overview) a été fusionnée avec /dashboard en v2.0


@dashboard_bp.get("/history")
def history():
    zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
    return render_template("history.html", zones=zones)


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
    zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
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
    zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
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

    # 4. Log
    try:
        from ..models import db as _db
        _db.session.add(JournalEntry(
            level="info",
            message=f"🌦 Profil météo de simulation changé : {profile}",
        ))
        _db.session.commit()
    except Exception:
        from ..models import db as _db
        _db.session.rollback()

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
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?")
    user = AdminUser.query.filter_by(username=username, enabled=True).first()
    from ..models import db
    if user and user.check_pin(pin):
        user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.add(JournalEntry(
                level="info",
                message=f"🔓 Connexion réussie : {username} ({ip})",
            ))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            log.warning("Échec log connexion : %s", e)
        session["auth_user"] = username
        session.permanent = True
        return redirect(next_url)
    # Échec d'authentification
    try:
        db.session.add(JournalEntry(
            level="warning",
            message=f"🔒 Échec de connexion : utilisateur «{username or 'vide'}» ({ip})",
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.warning("Échec log tentative connexion : %s", e)
    return render_template("login.html", next_url=next_url, error="Identifiant ou PIN incorrect.")


@dashboard_bp.get("/logout")
def logout():
    username = session.get("auth_user", "?")
    session.pop("auth_user", None)
    try:
        from ..models import db
        db.session.add(JournalEntry(
            level="info",
            message=f"🚪 Déconnexion : {username}",
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.warning("Échec log déconnexion : %s", e)
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


@dashboard_bp.post("/admin/reset_garden")
def admin_reset_garden():
    """Reset annuel : archive les plantations actives et réinitialise
    les zones aux valeurs par défaut. L'historique reste en DB pour
    le conseiller de rotation des cultures.
    """
    confirm = request.form.get("confirm", "").strip().upper()
    if confirm != "RESET":
        flash("Confirmation incorrecte — tape RESET en majuscules pour valider.", "danger")
        return redirect("/admin")

    # 1. Archiver toutes les plantations actives (status='archived')
    archived_count = 0
    for p in Planting.query.filter(Planting.status.in_(["active", "planned"])).all():
        p.status = "archived"
        archived_count += 1

    # 2. Réinitialiser les zones aux valeurs par défaut
    DEFAULTS = {
        1: ("Serre",     "Zone couverte avec toiture rétractable (vérin)", True,  30, 65, 15, 2.0, 1.0),
        2: ("Soleil",    "Plein terre, exposition plein sud",                False, 30, 65, 15, 2.0, 1.0),
        3: ("Mi-ombre",  "Plein terre, partiellement ombragée",              False, 30, 65, 15, 2.0, 1.0),
        4: ("Aromates",  "Plein terre, herbes et aromatiques",               False, 25, 55, 10, 2.0, 1.0),
    }
    for zone in Zone.query.all():
        d = DEFAULTS.get(zone.zone_id)
        if d:
            zone.name, zone.description, zone.has_roof = d[0], d[1], d[2]
            zone.moisture_threshold_low  = d[3]
            zone.moisture_threshold_high = d[4]
            zone.irrigation_duration_min = d[5]
            zone.length_m, zone.width_m  = d[6], d[7]
            zone.irrigation_mode = "auto"

    # 3. Journal
    db.session.add(JournalEntry(
        level="warning",
        message=f"♻️ RESET annuel : {archived_count} plantation(s) archivée(s), zones réinitialisées",
    ))
    db.session.commit()

    # 4. Supprimer le flag setup_done pour reproposer le wizard
    try:
        flag = _setup_done_path()
        if flag.exists():
            flag.unlink()
    except Exception as e:
        log.warning("Impossible de supprimer setup_done : %s", e)

    flash(
        f"♻️ Reset effectué : {archived_count} plantation(s) archivée(s) "
        f"(historique préservé pour les conseils de rotation). "
        f"Zones réinitialisées.",
        "success",
    )
    return redirect("/admin?reset=done")


def _setup_done_path():
    """Fichier flag pour savoir si l'onboarding est terminé."""
    from pathlib import Path
    return Path(current_app.root_path).parent / "data" / ".setup_done"


def _setup_skipped_path():
    """Fichier flag : l'utilisateur a explicitement masqué la bannière de bienvenue."""
    from pathlib import Path
    return Path(current_app.root_path).parent / "data" / ".setup_skipped"


@dashboard_bp.post("/setup/skip")
def setup_skip():
    """L'utilisateur masque la bannière de bienvenue (réversible via /admin)."""
    try:
        _setup_skipped_path().touch()
    except Exception as e:
        log.warning("Impossible de créer .setup_skipped : %s", e)
    return ("", 204)


@dashboard_bp.get("/setup")
def setup_wizard():
    """Wizard d'onboarding au premier lancement."""
    advisor = current_app.extensions.get("planting_advisor")
    plants_db = _load_plants_db()
    # Top 12 légumes faciles + populaires pour débutants
    easy_plants = sorted(
        [p for p in plants_db if p.get("difficulty") == "easy"],
        key=lambda p: p["name"],
    )[:18]
    zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
    return render_template(
        "setup.html",
        easy_plants=easy_plants,
        zones=zones,
        garden_name=current_app.config.get("GARDEN_NAME", "MonJardin"),
        garden_location=current_app.config.get("GARDEN_LOCATION", "Vullierens, Vaud"),
        garden_owner=current_app.config.get("GARDEN_OWNER", ""),
        latitude=current_app.config.get("GARDEN_LATITUDE", 46.778),
        longitude=current_app.config.get("GARDEN_LONGITUDE", 6.641),
    )


@dashboard_bp.post("/setup/save")
def setup_save():
    """Enregistre la configuration initiale du wizard."""
    form = request.form
    # 1. Identité jardin
    garden_name = form.get("garden_name", "").strip()
    garden_location = form.get("garden_location", "").strip()
    garden_owner = form.get("garden_owner", "").strip()
    if garden_name:    _update_env_var("GARDEN_NAME", garden_name)
    if garden_location: _update_env_var("GARDEN_LOCATION", garden_location)
    if garden_owner:   _update_env_var("GARDEN_OWNER", garden_owner)

    # 2. Coordonnées GPS
    try:
        lat = float(form.get("latitude", "46.778"))
        lon = float(form.get("longitude", "6.641"))
        _update_env_var("GARDEN_LATITUDE", str(lat))
        _update_env_var("GARDEN_LONGITUDE", str(lon))
    except ValueError:
        pass

    # 3. Configuration des zones
    for zone in Zone.query.order_by(Zone.display_order, Zone.zone_id).all():
        zid = zone.zone_id
        new_name = form.get(f"zone_{zid}_name", "").strip()
        if new_name:
            zone.name = new_name[:40]
        try:
            length = float(form.get(f"zone_{zid}_length", zone.length_m or 2.0))
            width  = float(form.get(f"zone_{zid}_width",  zone.width_m  or 1.0))
            if 0.1 <= length <= 50: zone.length_m = round(length, 2)
            if 0.1 <= width  <= 50: zone.width_m  = round(width, 2)
        except ValueError:
            pass
        zone.has_roof = (f"zone_{zid}_has_roof" in form)
    db.session.add(JournalEntry(
        level="info",
        message=f"⚙️ Configuration initiale terminée (wizard) — {garden_name or 'jardin'}",
    ))
    db.session.commit()

    # 4. Marquer le wizard comme fait
    try:
        flag = _setup_done_path()
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(datetime.now(timezone.utc).isoformat())
    except Exception as e:
        log.warning("Impossible de créer le flag setup_done : %s", e)

    flash("Configuration initiale enregistrée. Bienvenue dans MonJardin !", "success")
    return redirect("/dashboard")


@dashboard_bp.get("/rotation")
def rotation_page():
    """Vue Plan de rotation des cultures : zones × années."""
    advisor = current_app.extensions.get("rotation_advisor")
    zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
    plantings = Planting.query.all()

    today = date.today()
    years = [today.year, today.year - 1, today.year - 2]

    # Famille → couleur stable (pour rendu visuel)
    FAMILY_COLORS = {
        "Solanacées":      "#ef4444",
        "Cucurbitacées":   "#f59e0b",
        "Brassicacées":    "#8b5cf6",
        "Apiacées":        "#22c55e",
        "Alliacées":       "#0ea5e9",
        "Légumineuses":    "#16a34a",
        "Astéracées":      "#14b8a6",
        "Chénopodiacées":  "#a855f7",
        "Lamiacées":       "#84cc16",
        "Poacées":         "#eab308",
        "Valérianacées":   "#06b6d4",
        "Rosacées":        "#ec4899",
        "Boraginacées":    "#6366f1",
        "Tropaeolacées":   "#f97316",
        "Hydrophyllacées": "#94a3b8",
        "Asparagacées":    "#10b981",
        "Polygonacées":    "#d946ef",
        "Inconnue":        "#6b7280",
    }

    # Construire la grille : zones × années
    rotation_grid = []
    for zone in zones:
        per_year = advisor.get_zone_rotation_history_by_year(plantings, zone.zone_id, years=3) if advisor else {}
        row = {"zone": zone, "years": []}
        for y in years:
            cells = per_year.get(y, [])
            row["years"].append({
                "year": y,
                "families": cells,  # list of {family, names}
            })
        rotation_grid.append(row)

    # Famille active dans chaque zone (plantations actives)
    current_families_by_zone = {}
    for p in plantings:
        if p.status != "active":
            continue
        fam = advisor.family_of(p.vegetable_name) if advisor else "Inconnue"
        current_families_by_zone.setdefault(p.zone_id, set()).add(fam)

    return render_template(
        "rotation.html",
        rotation_grid=rotation_grid,
        years=years,
        family_colors=FAMILY_COLORS,
        current_families_by_zone={k: sorted(v) for k, v in current_families_by_zone.items()},
    )


@dashboard_bp.get("/plans")
def garden_plans_page():
    """Galerie de plans pré-faits applicables à une zone."""
    plans_path = Path(current_app.root_path).parent / "data" / "garden_plans.json"
    try:
        with open(plans_path, encoding="utf-8") as f:
            plans = json.load(f).get("plans", [])
    except Exception as e:
        log.warning("Plans non chargés : %s", e)
        plans = []
    # Enrichir chaque planting avec emoji
    plants_db = _load_plants_db()
    emoji_map = {p["name"]: p.get("emoji", "🌱") for p in plants_db}
    for plan in plans:
        for p in plan.get("plantings", []):
            p["emoji"] = emoji_map.get(p["vegetable_name"], "🌱")
    zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
    return render_template("plans.html", plans=plans, zones=zones)


@dashboard_bp.post("/plans/apply")
def garden_plans_apply():
    """Applique un plan pré-fait à une zone : crée toutes les plantations."""
    plan_id = request.form.get("plan_id", "")
    zone_id = request.form.get("zone_id", type=int)
    if not plan_id or not zone_id:
        flash("Plan ou zone manquant.", "danger")
        return redirect("/plans")

    zone = Zone.query.get(zone_id)
    if not zone:
        flash("Zone introuvable.", "danger")
        return redirect("/plans")

    plans_path = Path(current_app.root_path).parent / "data" / "garden_plans.json"
    try:
        with open(plans_path, encoding="utf-8") as f:
            plans = json.load(f).get("plans", [])
    except Exception:
        plans = []
    plan = next((p for p in plans if p["id"] == plan_id), None)
    if not plan:
        flash("Plan introuvable.", "danger")
        return redirect("/plans")

    advisor = current_app.extensions["planting_advisor"]
    today = date.today()

    # ── Vérifier les compatibilités de compagnonnage avant d'appliquer ──
    # Détecte les paires incompatibles à l'intérieur du plan ; n'arrête pas
    # mais avertit l'utilisateur via flash messages.
    plan_species = [e["vegetable_name"] for e in plan.get("plantings", [])]
    bad_pairs = []
    seen = set()
    for sp in plan_species:
        veg = advisor.get_vegetable(sp) or {}
        bad_companions = set(veg.get("bad_companions", []))
        for other in plan_species:
            if other == sp:
                continue
            pair = tuple(sorted([sp, other]))
            if pair in seen:
                continue
            if other in bad_companions:
                bad_pairs.append(pair)
                seen.add(pair)
    if bad_pairs:
        for a, b in bad_pairs:
            flash(f"⚠️ {a} et {b} sont incompatibles (mauvais voisinage)", "warning")

    # ── Auto-distribution sur la grille (case-par-case) ──
    # Récupère les cases déjà occupées par les plants actifs existants.
    CELL_CM = 30
    grid_cols = max(4, int((zone.length_m or 2.0) * 100 / CELL_CM))
    grid_rows = max(2, int((zone.width_m  or 1.0) * 100 / CELL_CM))
    occupied = set()
    for op in Planting.query.filter_by(zone_id=zone_id, status="active").all():
        ow, oh = max(1, op.grid_w or 1), max(1, op.grid_h or 1)
        for dr in range(oh):
            for dc in range(ow):
                occupied.add(((op.grid_row or 0) + dr, (op.grid_col or 0) + dc))
    # Itérateur de cases libres en row-major
    def _next_free():
        for r in range(grid_rows):
            for c in range(grid_cols):
                if (r, c) not in occupied:
                    yield (r, c)

    free_iter = _next_free()
    created = 0
    skipped = 0
    for entry in plan.get("plantings", []):
        veg_name = entry["vegetable_name"]
        veg = advisor.get_vegetable(veg_name)
        qty = max(1, min(50, int(entry.get("quantity", 1))))
        variety = entry.get("variety", "")
        for _ in range(qty):
            try:
                r, c = next(free_iter)
            except StopIteration:
                # Plus de case libre : on stoppe les ajouts de cette espèce
                skipped += qty - (created % qty if qty else 0)
                break
            occupied.add((r, c))
            db.session.add(Planting(
                zone_id=zone_id,
                vegetable_name=veg_name,
                variety=variety,
                planted_date=today,
                expected_harvest_date=None,
                water_need=(veg.get("water_need") if veg else "medium"),
                status="active",
                notes=f"Ajouté via le plan « {plan['name']} »",
                grid_row=r, grid_col=c, grid_w=1, grid_h=1,
            ))
            created += 1

    db.session.add(JournalEntry(
        level="info",
        message=f"📋 Plan « {plan['name']} » appliqué à {zone.name} : {created} plant(s) placé(s)"
                + (f" ({skipped} ignoré(s) — zone pleine)" if skipped else ""),
    ))
    db.session.commit()
    msg = f"Plan « {plan['name']} » appliqué : {created} plantation(s) ajoutée(s) dans {zone.name}."
    if skipped:
        msg += f" {skipped} plant(s) ignoré(s) car la zone est pleine."
    flash(msg, "success")
    return redirect(url_for("dashboard.zone_detail", zone_id=zone_id) + "#plants")


@dashboard_bp.get("/glossaire")
def glossary_page():
    """Glossaire des termes horticoles utilisés dans MonJardin."""
    glossary_path = Path(current_app.root_path).parent / "data" / "glossary.json"
    try:
        with open(glossary_path, encoding="utf-8") as f:
            data = json.load(f)
            terms = data.get("terms", [])
    except Exception as e:
        log.warning("Glossaire non chargé : %s", e)
        terms = []
    # Ordre éditorial des catégories (de la plus générale à la plus pointue)
    CAT_ORDER = ["Météo", "Climat", "Sol", "Familles botaniques", "Plantation", "Entretien",
                 "Maladies", "Traitements", "Calendrier lunaire"]
    def _cat_rank(c):
        try:    return CAT_ORDER.index(c)
        except ValueError: return len(CAT_ORDER)
    terms.sort(key=lambda t: (_cat_rank(t.get("category", "")), t.get("term", "")))
    # Grouper par catégorie en préservant l'ordre
    from collections import OrderedDict
    by_cat = OrderedDict()
    for t in terms:
        by_cat.setdefault(t.get("category", "Divers"), []).append(t)
    return render_template(
        "glossary.html",
        glossary_by_category=by_cat,
        total_terms=len(terms),
    )


@dashboard_bp.get("/conseils")
def conseils():
    advisor = current_app.extensions["planting_advisor"]
    current_month = date.today().month
    MONTH_NAMES_FR = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                      "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    seasonal_plants = advisor.get_seasonal_advice(current_month, limit=20)
    # Enrichir chaque légume avec son emoji depuis la DB plants
    plants_db = _load_plants_db()
    info_map = {p["name"]: p for p in plants_db}
    for v in seasonal_plants:
        if v["name"] in info_map:
            v["emoji"]    = info_map[v["name"]].get("emoji", "🌱")
            v["category"] = info_map[v["name"]].get("category", "légume")
            v["difficulty"] = info_map[v["name"]].get("difficulty", "medium")
    return render_template(
        "conseils.html",
        seasonal_plants=seasonal_plants,
        current_month=current_month,
        current_month_name=MONTH_NAMES_FR[current_month],
    )


@dashboard_bp.get("/about")
def about_page():
    return render_template("about.html")
