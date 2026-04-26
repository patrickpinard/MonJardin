"""Routes API JSON — consommées par le JavaScript du dashboard."""
import json
import logging
import threading
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request

from ..models import db, SensorReading, Zone, IrrigationLog, RoofLog, JournalEntry, Planting

api_bp = Blueprint("api", __name__)
log = logging.getLogger(__name__)

# M8 : lock global — une seule exécution de force_cycle() à la fois
_cycle_lock = threading.Lock()

def _utcnow() -> datetime:
    """M9 : remplacement de _utcnow() (deprecated Python 3.12+)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@api_bp.get("/data/current")
def current_data():
    """État courant : capteurs + actionneurs pour toutes les zones."""
    arduino = current_app.extensions["arduino_client"]
    sensor_data = arduino.get_all_sensors()
    actuator_status = arduino.get_actuator_status() or {"valves": [], "roof_state": "close"}

    # Construire le dict zones_data depuis sensor_data ou depuis la DB
    zones_map = {}
    if sensor_data:
        for z in sensor_data.get("zones", []):
            zones_map[z["zone_id"]] = z

    zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
    alert_since = _utcnow() - timedelta(hours=2)
    result = []
    for zone in zones:
        z_sensor = zones_map.get(zone.zone_id, {})
        # Dernière mesure en DB si Arduino injoignable
        if not z_sensor:
            last = (SensorReading.query
                    .filter_by(zone_id=zone.zone_id)
                    .order_by(SensorReading.timestamp.desc())
                    .first())
            z_sensor = {
                "soil_moisture_pct": last.soil_moisture_pct if last else 50.0,
                "raw_adc": last.raw_adc if last else 2048,
            }
        # Valve state
        valve_state = "close"
        for v in actuator_status.get("valves", []):
            if v.get("zone_id") == zone.zone_id:
                valve_state = v.get("state", "close")
                break
        # Alerte : zone sous seuil depuis 2h+
        recent = (SensorReading.query
                  .filter(SensorReading.zone_id == zone.zone_id,
                          SensorReading.timestamp >= alert_since)
                  .all())
        is_alerting = (len(recent) >= 3 and
                       all(r.soil_moisture_pct < zone.moisture_threshold_low for r in recent))
        # Légumes actifs
        plantings = Planting.query.filter_by(zone_id=zone.zone_id, status="active").all()
        result.append({
            **zone.to_dict(),
            "soil_moisture_pct": z_sensor.get("soil_moisture_pct", 50.0),
            "raw_adc": z_sensor.get("raw_adc"),
            "valve_state": valve_state,
            "is_alerting": is_alerting,
            "plantings": [p.to_dict() for p in plantings],
        })

    temp = sensor_data.get("temperature_c", 15.0) if sensor_data else 15.0
    wind = sensor_data.get("wind_speed_kmh") if sensor_data else None
    return jsonify({
        "zones": result,
        "temperature_c": temp,
        "temp_serre_c": sensor_data.get("temp_serre_c") if sensor_data else None,
        "wind_speed_kmh": wind,
        "roof_state": actuator_status.get("roof_state", "close"),
        "roof_target": actuator_status.get("roof_target"),
        "arduino_reachable": sensor_data is not None,
        "timestamp": _utcnow().isoformat(),
    })


@api_bp.get("/data/history")
def history():
    """Série temporelle pour Plotly (zone_id optionnel, hours=24 par défaut)."""
    zone_id = request.args.get("zone_id", type=int)
    # M6 : valider zone_id dans la plage [1..4]
    if zone_id is not None and zone_id not in (1, 2, 3, 4):
        return jsonify({"error": "zone_id doit être compris entre 1 et 4"}), 400
    try:
        # M5 : hours doit être > 0 (valeur négative produirait une date future)
        hours = min(max(int(request.args.get("hours", 24)), 1), 720)
    except (ValueError, TypeError):
        return jsonify({"error": "Le paramètre 'hours' doit être un entier positif"}), 400
    since = _utcnow() - timedelta(hours=hours)

    query = SensorReading.query.filter(SensorReading.timestamp >= since)
    if zone_id:
        query = query.filter_by(zone_id=zone_id)
    query = query.order_by(SensorReading.timestamp.asc())
    readings = query.all()

    # Grouper par zone
    by_zone: dict[int, list] = {}
    for r in readings:
        by_zone.setdefault(r.zone_id, []).append(r.to_dict())

    return jsonify({"zones": by_zone, "hours": hours})


@api_bp.get("/data/irrigation_events")
def irrigation_events():
    """Événements d'arrosage pour les marqueurs Plotly."""
    try:
        hours = min(max(int(request.args.get("hours", 24)), 1), 720)
    except (ValueError, TypeError):
        return jsonify({"error": "Le paramètre 'hours' doit être un entier positif"}), 400
    since = _utcnow() - timedelta(hours=hours)
    events = (IrrigationLog.query
              .filter(IrrigationLog.timestamp >= since)
              .order_by(IrrigationLog.timestamp.asc())
              .all())
    return jsonify({"events": [e.to_dict() for e in events]})


@api_bp.post("/control/valve/<int:zone_id>")
def control_valve(zone_id: int):
    """Commande manuelle d'une vanne."""
    zone = Zone.query.get(zone_id)
    if zone is None:
        return jsonify({"ok": False, "error": f"Zone {zone_id} inexistante"}), 404

    body = request.get_json(silent=True) or {}
    state = body.get("state", "")
    if state not in ("open", "close"):
        return jsonify({"ok": False, "error": "state doit être 'open' ou 'close'"}), 400

    arduino = current_app.extensions["arduino_client"]
    success = arduino.set_valve(zone_id, state)

    persist_warning = None
    auto_stop_min = None
    action_label = "Ouverture" if state == "open" else "Fermeture"
    if success:
        try:
            db.session.add(IrrigationLog(
                zone_id=zone_id, action=state,
                trigger_type="manual",
                reason="Commande manuelle utilisateur",
            ))
            db.session.add(JournalEntry(
                level="info",
                message=f"💧 {action_label} vanne {zone.name} (Z{zone_id}) — commande manuelle",
            ))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            log.error("Erreur persistance commande vanne zone %d : %s", zone_id, e)
            # M7 : informer le client que la commande a réussi mais le log a échoué
            persist_warning = "Commande exécutée, persistance en base échouée"

        # ── Sécurité : arrêt automatique après irrigation_duration_min ──
        scheduler = current_app.extensions.get("scheduler")
        job_id = f"auto_stop_valve_{zone_id}"
        if scheduler:
            # Toujours annuler un éventuel auto-stop précédent (replace_existing)
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass
            if state == "open":
                duration_min = max(1, int(zone.irrigation_duration_min or 15))
                auto_stop_min = duration_min
                from datetime import datetime, timezone, timedelta
                run_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=duration_min)
                _app = current_app._get_current_object()
                scheduler.add_job(
                    _auto_stop_valve,
                    "date",
                    run_date=run_at,
                    args=[_app, zone_id, duration_min],
                    id=job_id,
                    replace_existing=True,
                )

    action_label = "Ouverture" if state == "open" else "Fermeture"
    msg = f"{action_label} de la vanne d'arrosage {zone_id}" if success else "Échec commande Arduino"
    if success and state == "open" and auto_stop_min:
        msg += f" — arrêt automatique dans {auto_stop_min} min"
    resp = {
        "ok": success,
        "message": msg,
    }
    if persist_warning:
        resp["warning"] = persist_warning
    return jsonify(resp)


def _auto_stop_valve(app, zone_id: int, duration_min: int) -> None:
    """Job APScheduler : ferme la vanne après la durée max d'arrosage manuel."""
    with app.app_context():
        try:
            arduino = app.extensions["arduino_client"]
            # Vérifier que la vanne est encore ouverte (sinon rien à faire)
            status = arduino.get_actuator_status() or {"valves": []}
            still_open = any(
                v.get("zone_id") == zone_id and v.get("state") == "open"
                for v in status.get("valves", [])
            )
            if not still_open:
                log.info("Auto-stop zone %d : vanne déjà fermée, skip", zone_id)
                return
            arduino.set_valve(zone_id, "close")
            db.session.add(IrrigationLog(
                zone_id=zone_id, action="close",
                trigger_type="auto",
                reason=f"Arrêt automatique sécurité — durée max {duration_min} min atteinte",
            ))
            db.session.add(JournalEntry(
                level="warning",
                message=f"Zone {zone_id} — fermeture automatique vanne (sécurité, {duration_min} min)",
            ))
            db.session.commit()
            log.info("Auto-stop zone %d : vanne fermée après %d min", zone_id, duration_min)
        except Exception as e:
            log.error("Auto-stop zone %d échoué : %s", zone_id, e)


@api_bp.post("/control/roof")
def control_roof():
    """Commande manuelle du toit."""
    body = request.get_json(silent=True) or {}
    state = body.get("state", "")
    if state not in ("open", "close"):
        return jsonify({"ok": False, "error": "state doit être 'open' ou 'close'"}), 400

    arduino = current_app.extensions["arduino_client"]
    success = arduino.set_roof(state)

    action_label = "Ouverture" if state == "open" else "Fermeture"
    action_past  = "ouverte" if state == "open" else "fermée"
    if success:
        try:
            from ..models import RoofLog
            db.session.add(RoofLog(
                action=state, trigger_type="manual",
                reason=f"Lucarne {action_past} manuellement par l'utilisateur",
            ))
            db.session.add(JournalEntry(
                level="info",
                message=f"🪟 Lucarne {action_past} manuellement",
            ))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            log.error("Erreur persistance commande lucarne : %s", e)

    return jsonify({
        "ok": success,
        "message": f"{action_label} de la lucarne en cours…" if success else "Échec commande Arduino",
    })


@api_bp.post("/control/zone/<int:zone_id>/mode")
def set_zone_mode(zone_id: int):
    """Change le mode d'une zone (auto / manual / disabled)."""
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "")
    if mode not in ("auto", "manual", "disabled"):
        return jsonify({"ok": False, "error": "Mode invalide"}), 400
    zone = Zone.query.get_or_404(zone_id)
    zone.irrigation_mode = mode
    db.session.commit()
    return jsonify({"ok": True, "zone_id": zone_id, "mode": mode})


@api_bp.post("/zones/<int:zone_id>/plants/<int:plant_id>/move")
def plant_move(zone_id: int, plant_id: int):
    """Déplace un plant individuel vers (row, col) dans la grille de la zone.

    Body: {"row": int, "col": int}. Vérifie qu'il n'y a pas de collision avec
    d'autres plantings actifs (en tenant compte de leur grid_w/grid_h).
    """
    body = request.get_json(silent=True) or {}
    new_row = body.get("row")
    new_col = body.get("col")
    if not isinstance(new_row, int) or not isinstance(new_col, int) or new_row < 0 or new_col < 0:
        return jsonify({"ok": False, "error": "row/col doivent être des entiers positifs"}), 400

    p = Planting.query.filter_by(id=plant_id, zone_id=zone_id).first()
    if p is None:
        return jsonify({"ok": False, "error": "Plant introuvable dans cette zone"}), 404

    zone = Zone.query.get(zone_id)
    CELL_CM = 30
    cols = max(4, int((zone.length_m or 2.0) * 100 / CELL_CM))
    rows = max(2, int((zone.width_m  or 1.0) * 100 / CELL_CM))
    w, h = max(1, p.grid_w or 1), max(1, p.grid_h or 1)
    if new_col + w > cols or new_row + h > rows:
        return jsonify({"ok": False, "error": "Hors grille (taille ne rentre pas)"}), 400

    # Collision check vs autres plantings actifs
    target_cells = {(new_row + dr, new_col + dc) for dr in range(h) for dc in range(w)}
    others = Planting.query.filter(Planting.zone_id == zone_id,
                                   Planting.status == "active",
                                   Planting.id != p.id).all()
    for o in others:
        ow, oh = max(1, o.grid_w or 1), max(1, o.grid_h or 1)
        oc, orow = (o.grid_col or 0), (o.grid_row or 0)
        for dr in range(oh):
            for dc in range(ow):
                if (orow + dr, oc + dc) in target_cells:
                    return jsonify({"ok": False,
                                    "error": f"Case (L{orow+dr+1}, C{oc+dc+1}) occupée par {o.vegetable_name}"}), 409

    p.grid_row = new_row
    p.grid_col = new_col
    db.session.commit()
    return jsonify({"ok": True, "id": plant_id, "row": new_row, "col": new_col})


@api_bp.post("/zones/<int:zone_id>/plants/reorder")
def plants_reorder(zone_id: int):
    """Réordonne les groupes (espèce + variété) actifs d'une zone via le plan visuel.

    Body : {"order": [rep_id_1, rep_id_2, ...]} où chaque rep_id est l'id du
    représentant d'un groupe (vegetable_name, variety) — celui retourné dans
    plant_species_summary[].rep_id.

    Toutes les plantations actives partageant la même (vegetable_name, variety)
    que le rep_id reçoivent display_order = position dans la liste.
    """
    if not Zone.query.get(zone_id):
        return jsonify({"ok": False, "error": f"Zone {zone_id} inexistante"}), 404

    body = request.get_json(silent=True) or {}
    order = body.get("order", [])
    if not isinstance(order, list) or not all(isinstance(x, int) for x in order):
        return jsonify({"ok": False, "error": "order doit être une liste d'entiers (rep_id)"}), 400

    # Charger toutes les plantations actives de la zone
    actives = Planting.query.filter_by(zone_id=zone_id, status="active").all()
    by_id   = {p.id: p for p in actives}

    # Identifier chaque rep_id et son groupe (vegetable_name, variety)
    seen_groups = set()
    for idx, rep_id in enumerate(order):
        rep = by_id.get(rep_id)
        if rep is None:
            continue  # rep inconnu (peut arriver si la page a vieilli) — on ignore
        key = (rep.vegetable_name, (rep.variety or "").strip())
        if key in seen_groups:
            continue  # déjà traité
        seen_groups.add(key)
        # Tous les plantings du même groupe reçoivent le même display_order
        for p in actives:
            if (p.vegetable_name, (p.variety or "").strip()) == key:
                p.display_order = idx + 1

    db.session.commit()
    return jsonify({"ok": True, "zone_id": zone_id, "order": order, "groups_updated": len(seen_groups)})


@api_bp.post("/zones/reorder")
def zones_reorder():
    """Réordonne les zones d'après une liste de zone_id (drag & drop dashboard)."""
    body = request.get_json(silent=True) or {}
    order = body.get("order", [])
    if not isinstance(order, list) or not all(isinstance(x, int) for x in order):
        return jsonify({"ok": False, "error": "Format invalide : order doit être une liste d'entiers"}), 400

    zones = {z.zone_id: z for z in Zone.query.all()}
    if set(order) != set(zones.keys()):
        return jsonify({
            "ok": False,
            "error": "Liste incomplète ou contient des zones inconnues",
            "expected": sorted(zones.keys()),
            "received": order,
        }), 400

    for idx, zid in enumerate(order):
        zones[zid].display_order = idx + 1
    db.session.commit()
    return jsonify({"ok": True, "order": order})


@api_bp.get("/weather/current")
def weather_current():
    weather_svc = current_app.extensions["weather_service"]
    return jsonify(weather_svc.get_current())


@api_bp.get("/weather/forecast")
def weather_forecast():
    weather_svc = current_app.extensions["weather_service"]
    return jsonify({"forecast": weather_svc.get_forecast_48h()})


@api_bp.get("/system/ping")
def system_ping():
    """Ping rapide pour le monitor de connexion Arduino (sidebar)."""
    import time
    arduino = current_app.extensions["arduino_client"]
    t0 = time.perf_counter()
    health = arduino.get_health()
    latency_ms = round((time.perf_counter() - t0) * 1000)
    return jsonify({
        "ok": health is not None,
        "latency_ms": latency_ms,
        "simulation_mode": current_app.config.get("SIMULATION_MODE", False),
    })


@api_bp.get("/system/health")
def system_health():
    arduino = current_app.extensions["arduino_client"]
    health = arduino.get_health()
    last_reading = SensorReading.query.order_by(SensorReading.timestamp.desc()).first()
    return jsonify({
        "arduino_reachable": health is not None,
        "arduino_health": health,
        "consecutive_failures": arduino.consecutive_failures,
        "last_reading": last_reading.timestamp.isoformat() if last_reading else None,
        "simulation_mode": current_app.config.get("SIMULATION_MODE", False),
        "sim_speed": current_app.config.get("SIMULATION_SPEED", 1),
    })


@api_bp.get("/system/arduino")
def arduino_system():
    """Diagnostic Arduino — MCU, mémoire, flash, WiFi, uptime."""
    arduino = current_app.extensions["arduino_client"]
    health = arduino.get_health()
    if health is None:
        return jsonify({"reachable": False}), 503
    health["reachable"] = True

    # Calculs dérivés pour l'affichage
    sram_total = health.get("sram_total_bytes", 0)
    sram_used  = health.get("sram_used_bytes",  0)
    if sram_total > 0:
        health["sram_pct"] = round(sram_used / sram_total * 100, 1)

    flash_total = health.get("flash_total_bytes", 0)
    flash_used  = health.get("flash_used_bytes",  0)
    if flash_total > 0:
        health["flash_pct"] = round(flash_used / flash_total * 100, 1)

    return jsonify(health)


@api_bp.get("/system/rpi")
def rpi_status():
    """Diagnostic Raspberry Pi — CPU, mémoire, disques, réseau."""
    import platform, socket, sys, time, os
    from datetime import datetime, timezone

    info = {
        "hostname": socket.gethostname(),
        "os": platform.platform(terse=True),
        "kernel": platform.release(),
        "python_version": sys.version.split()[0],
        "current_time": datetime.now(timezone.utc).isoformat(),
    }

    try:
        import psutil
        info["cpu_percent"]  = psutil.cpu_percent(interval=0.2)
        info["cpu_count"]    = psutil.cpu_count(logical=False)
        info["cpu_freq_mhz"] = psutil.cpu_freq().current if psutil.cpu_freq() else None
        load = psutil.getloadavg()
        info["load_avg"] = [round(l, 2) for l in load]
        info["uptime_s"] = int(time.time() - psutil.boot_time())

        # CPU temperature (RPi-specific)
        try:
            temps = psutil.sensors_temperatures()
            cpu_t = temps.get("cpu_thermal") or temps.get("coretemp") or []
            info["cpu_temp_c"] = round(cpu_t[0].current, 1) if cpu_t else None
        except Exception as e:
            log.debug("psutil sensors_temperatures indisponible : %s", e)
            try:
                with open("/sys/class/thermal/thermal_zone0/temp") as f:
                    info["cpu_temp_c"] = round(int(f.read()) / 1000, 1)
            except Exception as e2:
                log.debug("Lecture thermal_zone0 indisponible : %s", e2)
                info["cpu_temp_c"] = None

        # Simulated temperature in simulation mode when sensor unavailable
        if info["cpu_temp_c"] is None and current_app.config.get("SIMULATION_MODE"):
            import random
            base = 42.0 + info["cpu_percent"] * 0.18
            info["cpu_temp_c"] = round(base + random.gauss(0, 0.5), 1)

        # Memory
        mem = psutil.virtual_memory()
        info["memory"] = {
            "total": mem.total, "used": mem.used,
            "available": mem.available, "percent": mem.percent,
        }

        # Disks
        disks = []
        for part in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total": u.total, "used": u.used,
                    "free": u.free, "percent": u.percent,
                })
            except PermissionError:
                pass
        info["disks"] = disks

        # Network
        addrs = psutil.net_if_addrs()
        io    = psutil.net_io_counters(pernic=True)
        net = []
        for iface, addr_list in addrs.items():
            if iface == "lo":
                continue
            ipv4 = next((a.address for a in addr_list if a.family == 2), None)
            ipv6 = next((a.address for a in addr_list if a.family == 10), None)
            ioc = io.get(iface)
            net.append({
                "interface":   iface,
                "address":     ipv4,
                "address6":    ipv6,
                "bytes_sent":  ioc.bytes_sent if ioc else 0,
                "bytes_recv":  ioc.bytes_recv if ioc else 0,
            })
        info["network"] = net

    except ImportError:
        info["cpu_percent"] = 0; info["cpu_count"] = 4
        info["cpu_freq_mhz"] = 1800; info["cpu_temp_c"] = None
        info["load_avg"] = [0, 0, 0]
        info["uptime_s"] = 0
        info["memory"] = {"total": 8*1024**3, "used": 2*1024**3, "available": 6*1024**3, "percent": 25.0}
        info["disks"] = [{"mountpoint": "/", "fstype": "ext4", "total": 32*1024**3, "used": 8*1024**3, "free": 24*1024**3, "percent": 25.0}]
        info["network"] = [{"interface": "eth0", "address": socket.gethostbyname(socket.gethostname()), "address6": None, "bytes_sent": 0, "bytes_recv": 0}]

    return jsonify(info)


@api_bp.post("/system/force_cycle")
def force_cycle():
    """Déclenche immédiatement un cycle d'automatisation."""
    # M8 : lock non-bloquant — rejette les appels concurrents (429)
    if not _cycle_lock.acquire(blocking=False):
        return jsonify({"ok": False, "message": "Un cycle est déjà en cours"}), 429
    try:
        db.session.add(JournalEntry(
            level="info",
            message="🔄 Cycle d'automatisation forcé manuellement",
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
    from ..services.scheduler import automation_cycle
    app_ref = current_app._get_current_object()
    def _run():
        try:
            automation_cycle(app_ref)
        finally:
            _cycle_lock.release()
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "Cycle déclenché"})


@api_bp.post("/arduino/log")
def arduino_log():
    """Reçoit les logs de l'Arduino et les persiste en JournalEntry."""
    body = request.get_json(silent=True) or {}
    logs = body.get("logs", [])
    if not logs:
        return jsonify({"ok": True, "stored": 0})
    stored = 0
    try:
        for line in logs[:50]:  # max 50 lignes par batch
            if not isinstance(line, str):
                continue
            level = "info"
            if "[ERROR]" in line:   level = "danger"
            elif "[WARNING]" in line: level = "warning"
            db.session.add(JournalEntry(
                level=level,
                message=f"[Arduino] {line[:255]}",
            ))
            stored += 1
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error("Erreur persistance logs Arduino : %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "stored": stored})


@api_bp.post("/arduino/alert")
def arduino_alert():
    """Reçoit une alerte de l'Arduino et envoie un email à l'administrateur."""
    body = request.get_json(silent=True) or {}
    zone_id = body.get("zone_id")
    message = body.get("message", "Alerte Arduino")
    alert_type = body.get("type", "unknown")

    log.warning("ALERTE Arduino zone=%s type=%s : %s", zone_id, alert_type, message)

    try:
        db.session.add(JournalEntry(
            level="danger",
            message=f"[Arduino ALERTE] {message}",
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error("Erreur persistance alerte Arduino : %s", e)

    from ..services.email_builder import build_email_html
    html = build_email_html(
        title=f"Alerte Arduino — {alert_type}",
        intro=message,
        rows=[
            ("Zone", str(zone_id) if zone_id else "—"),
            ("Type d'alerte", alert_type),
        ],
        level="alert",
        footer_note="Connectez-vous à MonJardin pour vérifier l'état de votre jardin.",
    )
    _send_alert_email(
        subject=f"MonJardin — Alerte Arduino : {alert_type}",
        body_plain=f"{message}\n\nZone : {zone_id}\nType : {alert_type}",
        body_html=html,
    )

    return jsonify({"ok": True})


def _send_alert_email(subject: str, body_plain: str, body_html: str = None,
                      to: str = None):
    """Envoie un email HTML+texte. Retourne (ok: bool, error: str|None)."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    SMTP_HOST     = current_app.config.get("SMTP_HOST", "smtp.bluewin.ch")
    SMTP_PORT     = int(current_app.config.get("SMTP_PORT", 587))
    SMTP_USER     = current_app.config.get("SMTP_USER", "")
    SMTP_PASSWORD = current_app.config.get("SMTP_PASSWORD", "")
    FROM          = current_app.config.get("MAIL_DEFAULT_SENDER", SMTP_USER)
    USE_TLS       = current_app.config.get("MAIL_USE_TLS", True)
    DEST          = to or current_app.config.get("ADMIN_NOTIFICATION_EMAIL", "ppinard@bluewin.ch")

    if not SMTP_USER or not SMTP_PASSWORD:
        msg = "SMTP non configuré (SMTP_USER/SMTP_PASSWORD manquants)"
        log.warning("%s — email non envoyé", msg)
        return False, msg
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = FROM
        msg["To"]      = DEST
        msg.attach(MIMEText(body_plain, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            if USE_TLS:
                smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        log.info("Email envoyé à %s : %s", DEST, subject)
        return True, None
    except Exception as e:
        log.error("Échec envoi email : %s", e)
        return False, str(e)


@api_bp.post("/system/test_email")
def test_email():
    """Envoie un email de test pour vérifier la configuration SMTP."""
    from datetime import datetime
    from ..services.email_builder import build_email_html
    DEST  = current_app.config.get("ADMIN_NOTIFICATION_EMAIL", "ppinard@bluewin.ch")
    HOST  = current_app.config.get("SMTP_HOST", "")
    PORT  = current_app.config.get("SMTP_PORT", 587)
    FROM  = current_app.config.get("MAIL_DEFAULT_SENDER", "")
    now   = datetime.now().strftime("%d.%m.%Y à %H:%M:%S")

    html = build_email_html(
        title="Test de la configuration email",
        intro="Ceci est un email de test envoyé depuis votre système MonJardin. "
              "Si vous recevez ce message, les alertes sont correctement configurées.",
        rows=[
            ("Date", now),
            ("Serveur SMTP", f"{HOST}:{PORT}"),
            ("Expéditeur", FROM),
            ("Destinataire", DEST),
            ("TLS", "Activé" if current_app.config.get("MAIL_USE_TLS", True) else "Désactivé"),
        ],
        level="success",
        footer_note="Ce message a été envoyé automatiquement. Aucune action n'est requise.",
    )
    plain = (f"Test email MonJardin\n\nDate : {now}\n"
             f"Serveur : {HOST}:{PORT}\nExpéditeur : {FROM}\nDestinataire : {DEST}\n\n"
             "Configuration email correcte.")
    ok, err = _send_alert_email(
        subject="MonJardin — Test de la configuration email",
        body_plain=plain, body_html=html, to=DEST,
    )
    if ok:
        return jsonify({"ok": True, "to": DEST})
    return jsonify({"ok": False, "error": err}), 500


@api_bp.get("/notifications")
def notifications():
    """Notifications pertinentes pour l'utilisateur, triées par importance."""
    now = _utcnow()
    results = []
    seen_ids = set()

    def _add(nid, ts, level, message, kind):
        if nid not in seen_ids:
            seen_ids.add(nid)
            results.append({"id": nid,
                            "timestamp": ts.isoformat() if ts else None,
                            "level": level, "message": message, "kind": kind})

    # 1. danger/error entries — 7 derniers jours (priorité max)
    for e in (JournalEntry.query
              .filter(JournalEntry.level.in_(["danger", "error"]),
                      JournalEntry.timestamp >= now - timedelta(days=7))
              .order_by(JournalEntry.timestamp.desc()).limit(20).all()):
        _add(f"je-{e.id}", e.timestamp, e.level, e.message, "system")

    # 2. warning entries — 48 dernières heures
    for e in (JournalEntry.query
              .filter(JournalEntry.level == "warning",
                      JournalEntry.timestamp >= now - timedelta(hours=48))
              .order_by(JournalEntry.timestamp.desc()).limit(15).all()):
        _add(f"je-{e.id}", e.timestamp, "warning", e.message, "system")

    # 3. Arrosages d'urgence (gel, canicule, météo) — 7 derniers jours
    # Dédupliqués par tranche de 5 minutes (un seul par cycle d'automatisation)
    seen_irr_slots: set = set()
    emergency_raw = (IrrigationLog.query
                     .filter(IrrigationLog.trigger_type.in_(["frost", "heatwave", "weather"]),
                             IrrigationLog.timestamp >= now - timedelta(days=7))
                     .order_by(IrrigationLog.timestamp.desc()).limit(50).all())
    for e in emergency_raw:
        slot = e.timestamp.strftime("%Y-%m-%d %H:%M") if e.timestamp else "?"
        slot = slot[:-1] + "0"  # arrondi à 10 min
        key = f"{e.trigger_type}-{slot}"
        if key in seen_irr_slots:
            continue
        seen_irr_slots.add(key)
        icons = {"frost": "❄️", "heatwave": "🌡️", "weather": "🌦️"}
        icon = icons.get(e.trigger_type, "💧")
        lvl = "danger" if e.trigger_type == "frost" else "warning"
        msg = e.reason or f"Zone {e.zone_id} — {e.trigger_type}"
        _add(f"il-{e.id}", e.timestamp, lvl, f"{icon} {msg}", "irrigation")
        if len(seen_irr_slots) >= 5:
            break

    # 4. Arrosages manuels — 24 dernières heures (ouvertures seulement)
    for e in (IrrigationLog.query
              .filter(IrrigationLog.trigger_type == "manual",
                      IrrigationLog.action == "open",
                      IrrigationLog.timestamp >= now - timedelta(hours=24))
              .order_by(IrrigationLog.timestamp.desc()).limit(5).all()):
        _add(f"il-{e.id}", e.timestamp, "info",
             f"💧 Arrosage manuel démarré — Zone {e.zone_id}", "irrigation")

    # 5. Changements d'état de la lucarne — seulement les transitions (open↔close)
    roof_recent = (RoofLog.query
                   .filter(RoofLog.timestamp >= now - timedelta(hours=48))
                   .order_by(RoofLog.timestamp.desc()).limit(200).all())
    last_roof_action = None
    transitions_added = 0
    for e in roof_recent:
        if e.action != last_roof_action:
            action_fr = "ouverte" if e.action == "open" else "fermée"
            icon = "🔓" if e.action == "open" else "🔒"
            msg = e.reason or f"Lucarne {action_fr}"
            _add(f"rl-{e.id}", e.timestamp, "info", f"{icon} {msg}", "roof")
            last_roof_action = e.action
            transitions_added += 1
            if transitions_added >= 4:
                break

    # Tri par timestamp desc, limite 30
    results.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return jsonify({"entries": results[:30]})


_TEST_ALERTS = {
    "frost": {
        "subject": "MonJardin — Alerte gel nocturne",
        "title":   "Gel nocturne détecté",
        "intro":   "La température extérieure est descendue sous le seuil critique. "
                   "Les vannes ont été fermées automatiquement et la lucarne de serre fermée.",
        "rows":    [("Température mesurée", "-2.3°C"), ("Seuil d'alerte", "3°C"),
                    ("Zones protégées", "1, 2, 3, 4"), ("Action effectuée", "Fermeture toutes vannes + lucarne")],
        "level":   "alert",
        "footer":  "Vérifiez l'état de vos plantes sensibles au gel.",
        "journal": ("danger", "🌡️ Gel nocturne détecté — T°=-2.3°C, vannes fermées, lucarne fermée"),
    },
    "drought": {
        "subject": "MonJardin — Alerte sécheresse critique",
        "title":   "Sécheresse critique — Zone 2",
        "intro":   "Le capteur de la zone Soleil indique un niveau d'humidité critique malgré "
                   "deux cycles d'arrosage consécutifs. Intervention manuelle recommandée.",
        "rows":    [("Zone", "2 — Soleil"), ("Humidité mesurée", "12%"), ("Seuil bas", "30%"),
                    ("Arrosages tentés", "2 × 15 min"), ("Dernière lecture", "il y a 5 min")],
        "level":   "alert",
        "footer":  "Vérifiez le capteur et la vanne de la zone Soleil.",
        "journal": ("danger", "💧 Sécheresse critique zone 2 (Soleil) — 12%, 2 arrosages sans effet"),
    },
    "sensor_failure": {
        "subject": "MonJardin — Capteur hors service",
        "title":   "Capteur défaillant — Zone 3",
        "intro":   "Aucune donnée reçue du capteur d'humidité de la zone Mi-ombre depuis 2h15. "
                   "La zone est passée en mode manuel par sécurité.",
        "rows":    [("Zone", "3 — Mi-ombre"), ("Dernière donnée valide", "il y a 2h15"),
                    ("Valeur ADC brute", "4095 (hors plage)"), ("Mode activé", "Manuel (sécurité)")],
        "level":   "warning",
        "footer":  "Vérifiez le câblage du capteur SoilWatch 10 de la zone Mi-ombre.",
        "journal": ("warning", "🔌 Capteur HS zone 3 (Mi-ombre) — aucune donnée depuis 2h15"),
    },
    "flood": {
        "subject": "MonJardin — Risque d'inondation serre",
        "title":   "Humidité excessive — Zone 1 Serre",
        "intro":   "Le sol de la serre est saturé. La vanne est fermée et un délai de 3h "
                   "est imposé avant tout arrosage automatique.",
        "rows":    [("Zone", "1 — Serre"), ("Humidité mesurée", "94%"), ("Seuil haut", "65%"),
                    ("Vanne", "Fermée"), ("Prochaine évaluation", "dans 3h")],
        "level":   "warning",
        "footer":  "Vérifiez le drainage et réduisez les fréquences d'arrosage.",
        "journal": ("warning", "🌊 Sol saturé zone 1 (Serre) — 94%, arrosage suspendu 3h"),
    },
    "arduino_offline": {
        "subject": "MonJardin — Arduino injoignable",
        "title":   "Perte de connexion Arduino",
        "intro":   "L'Arduino Edge Control ne répond plus depuis 15 tentatives consécutives. "
                   "Le mode failsafe a été activé : toutes les vannes ont été fermées.",
        "rows":    [("Tentatives échouées", "15"), ("Dernier contact", "il y a 8 min"),
                    ("Adresse", "192.168.1.100:80"), ("Action failsafe", "Fermeture toutes vannes")],
        "level":   "alert",
        "footer":  "Vérifiez l'alimentation et la connexion WiFi de l'Arduino.",
        "journal": ("danger", "📡 Arduino injoignable — 15 échecs, failsafe activé"),
    },
}


@api_bp.post("/system/test_alert/<alert_type>")
def test_alert_email(alert_type: str):
    """Envoie un email d'alerte de test selon le type choisi."""
    from ..services.email_builder import build_email_html
    cfg = _TEST_ALERTS.get(alert_type)
    if not cfg:
        return jsonify({"ok": False, "error": f"Type inconnu : {alert_type}"}), 400

    html = build_email_html(
        title=cfg["title"], intro=cfg["intro"],
        rows=cfg["rows"], level=cfg["level"], footer_note=cfg["footer"],
    )
    ok, err = _send_alert_email(
        subject=cfg["subject"],
        body_plain=f"{cfg['title']}\n\n{cfg['intro']}",
        body_html=html,
    )
    if not ok:
        return jsonify({"ok": False, "error": err}), 500

    # Ajoute au journal pour simuler une vraie alerte
    try:
        lvl, msg = cfg["journal"]
        db.session.add(JournalEntry(level=lvl, message=f"[TEST] {msg}"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify({"ok": True, "type": alert_type})


@api_bp.get("/journal")
def journal():
    """10 dernières entrées du journal système."""
    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except (ValueError, TypeError):
        return jsonify({"error": "Le paramètre 'limit' doit être un entier"}), 400
    entries = (JournalEntry.query
               .order_by(JournalEntry.timestamp.desc())
               .limit(limit).all())
    return jsonify({"entries": [e.to_dict() for e in entries]})


@api_bp.post("/journal/purge")
def purge_journal():
    """Purge tous les événements (arrosage, lucarne, journal) antérieurs à une date."""
    body = request.get_json(silent=True) or {}
    before_str = body.get("before_date", "")
    try:
        before_dt = datetime.strptime(before_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Format attendu : YYYY-MM-DD"}), 400

    try:
        n_irr = IrrigationLog.query.filter(IrrigationLog.timestamp < before_dt)\
                    .delete(synchronize_session=False)
        n_roof = RoofLog.query.filter(RoofLog.timestamp < before_dt)\
                    .delete(synchronize_session=False)
        n_sys = JournalEntry.query.filter(JournalEntry.timestamp < before_dt)\
                    .delete(synchronize_session=False)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    total = n_irr + n_roof + n_sys
    return jsonify({"ok": True, "deleted": {"irrigation": n_irr, "roof": n_roof, "system": n_sys}, "total": total})


@api_bp.get("/rotation/<int:zone_id>/<path:vegetable_name>")
def rotation_check(zone_id: int, vegetable_name: str):
    """Vérifie le conflit de rotation pour un légume dans une zone donnée.

    Retourne :
    - conflict : null OU {level, family, previous, days_ago, message}
    - best_zone : suggestion de meilleure zone (alternative si conflict)
    """
    advisor = current_app.extensions.get("rotation_advisor")
    if advisor is None:
        return jsonify({"conflict": None, "best_zone": None})

    plantings = Planting.query.all()
    conflict = advisor.check_conflict(plantings, zone_id, vegetable_name)

    best = None
    if conflict and conflict.get("level") == "danger":
        zones = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
        best = advisor.suggest_best_zone(plantings, zones, vegetable_name)
        # N'afficher que si la suggestion est différente et meilleure
        if best and (best["zone_id"] == zone_id or not best.get("is_safe")):
            best = None
    return jsonify({
        "zone_id": zone_id,
        "vegetable_name": vegetable_name,
        "family": advisor.family_of(vegetable_name),
        "conflict": conflict,
        "best_zone": best,
    })
