"""Routes API JSON — consommées par le JavaScript du dashboard."""
import json
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

from ..models import db, SensorReading, Zone, IrrigationLog, RoofLog, JournalEntry, Planting

api_bp = Blueprint("api", __name__)


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

    zones = Zone.query.order_by(Zone.zone_id).all()
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
        # Légumes actifs
        plantings = Planting.query.filter_by(zone_id=zone.zone_id, status="active").all()
        result.append({
            **zone.to_dict(),
            "soil_moisture_pct": z_sensor.get("soil_moisture_pct", 50.0),
            "raw_adc": z_sensor.get("raw_adc"),
            "valve_state": valve_state,
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
        "arduino_reachable": sensor_data is not None,
        "timestamp": datetime.utcnow().isoformat(),
    })


@api_bp.get("/data/history")
def history():
    """Série temporelle pour Plotly (zone_id optionnel, hours=24 par défaut)."""
    zone_id = request.args.get("zone_id", type=int)
    hours = min(int(request.args.get("hours", 24)), 720)
    since = datetime.utcnow() - timedelta(hours=hours)

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
    hours = min(int(request.args.get("hours", 24)), 720)
    since = datetime.utcnow() - timedelta(hours=hours)
    events = (IrrigationLog.query
              .filter(IrrigationLog.timestamp >= since)
              .order_by(IrrigationLog.timestamp.asc())
              .all())
    return jsonify({"events": [e.to_dict() for e in events]})


@api_bp.post("/control/valve/<int:zone_id>")
def control_valve(zone_id: int):
    """Commande manuelle d'une vanne."""
    body = request.get_json(silent=True) or {}
    state = body.get("state", "")
    if state not in ("open", "close"):
        return jsonify({"ok": False, "error": "state doit être 'open' ou 'close'"}), 400

    arduino = current_app.extensions["arduino_client"]
    success = arduino.set_valve(zone_id, state)

    if success:
        entry = IrrigationLog(
            zone_id=zone_id, action=state,
            trigger_type="manual",
            reason=f"Commande manuelle utilisateur",
        )
        journal = JournalEntry(
            level="info",
            message=f"Zone {zone_id} — vanne {state} (commande manuelle)",
        )
        db.session.add(entry)
        db.session.add(journal)
        db.session.commit()

    action_fr = "ouverte" if state == "open" else "fermée"
    return jsonify({
        "ok": success,
        "message": f"Vanne zone {zone_id} {action_fr}" if success else "Échec commande Arduino",
    })


@api_bp.post("/control/roof")
def control_roof():
    """Commande manuelle du toit."""
    body = request.get_json(silent=True) or {}
    state = body.get("state", "")
    if state not in ("open", "close"):
        return jsonify({"ok": False, "error": "state doit être 'open' ou 'close'"}), 400

    arduino = current_app.extensions["arduino_client"]
    success = arduino.set_roof(state)

    if success:
        from ..models import RoofLog
        db.session.add(RoofLog(action=state, trigger_type="manual", reason="Commande manuelle utilisateur"))
        db.session.add(JournalEntry(level="info", message=f"Lucarne — {state} (commande manuelle)"))
        db.session.commit()

    action_fr = "ouvert" if state == "open" else "fermé"
    return jsonify({
        "ok": success,
        "message": f"Lucarne {action_fr}" if success else "Échec commande Arduino",
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
        except Exception:
            try:
                with open("/sys/class/thermal/thermal_zone0/temp") as f:
                    info["cpu_temp_c"] = round(int(f.read()) / 1000, 1)
            except Exception:
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
    from ..services.scheduler import automation_cycle
    import threading
    t = threading.Thread(target=automation_cycle, args=[current_app._get_current_object()])
    t.daemon = True
    t.start()
    return jsonify({"ok": True, "message": "Cycle déclenché"})


@api_bp.get("/journal")
def journal():
    """10 dernières entrées du journal système."""
    limit = min(int(request.args.get("limit", 20)), 100)
    entries = (JournalEntry.query
               .order_by(JournalEntry.timestamp.desc())
               .limit(limit).all())
    return jsonify({"entries": [e.to_dict() for e in entries]})
