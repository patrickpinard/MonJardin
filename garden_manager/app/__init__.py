"""Factory Flask — MonJardin."""
import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_cors import CORS

from .config import Config
from .models.database import db

log = logging.getLogger(__name__)


def create_app(config: type = Config) -> Flask:
    """Crée et configure l'application Flask."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config)

    CORS(app)
    db.init_app(app)

    # WAL mode for concurrent read/write (scheduler + web requests)
    from sqlalchemy import event, text
    from sqlalchemy.engine import Engine
    import sqlite3

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _connection_record):
        if isinstance(dbapi_conn, sqlite3.Connection):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA busy_timeout=5000")

    with app.app_context():
        # Importer tous les modèles pour que create_all les voie
        from .models import (SensorReading, Zone, IrrigationLog, RoofLog,
                             JournalEntry, Planting, WeatherCache, AdminUser,
                             AlertRecipient, ZonePhoto)
        # Création des tables (y compris admin_users)
        db.create_all()
        # Migrations colonnes manquantes (ALTER TABLE si nécessaire)
        _migrate_db(app)
        # Données initiales
        from .seed import ensure_defaults, seed_demo_history
        ensure_defaults(app)
        if app.config.get("SIMULATION_MODE", False):
            seed_demo_history(app)

    # Protection par authentification (before_request global)
    _setup_auth(app)

    # Initialisation des services (singletons stockés dans app.extensions)
    _init_services(app)

    # Enregistrement des blueprints
    from .api.routes_dashboard import dashboard_bp
    from .api.routes_api import api_bp
    from .api.routes_config import config_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(config_bp)

    # Démarrage du planificateur
    _start_scheduler(app)

    # ── Filtre Jinja : conversion UTC (DB) → heure locale Europe/Zurich ──
    # Toutes les colonnes timestamp/created_at sont stockées en UTC naïf
    # (datetime.now(timezone.utc).replace(tzinfo=None)). Pour l'affichage
    # on les rebascule vers le fuseau local du jardin (Vullierens = Europe/Zurich).
    from datetime import timezone as _tz
    try:
        from zoneinfo import ZoneInfo
        _LOCAL_TZ = ZoneInfo("Europe/Zurich")
    except Exception:
        _LOCAL_TZ = _tz.utc  # fallback
    def _to_local(dt):
        if dt is None:
            return None
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=_tz.utc)
        return dt.astimezone(_LOCAL_TZ)
    @app.template_filter("localtime")
    def _filter_localtime(dt, fmt="%d.%m.%Y %H:%M"):
        d = _to_local(dt)
        return d.strftime(fmt) if d else ""
    @app.template_filter("localdate")
    def _filter_localdate(dt, fmt="%d.%m.%Y"):
        d = _to_local(dt)
        return d.strftime(fmt) if d else ""
    @app.template_filter("localhour")
    def _filter_localhour(dt, fmt="%H:%M"):
        d = _to_local(dt)
        return d.strftime(fmt) if d else ""

    # Contexte global pour les templates
    @app.context_processor
    def inject_globals():
        from .models import Zone
        try:
            zones_nav = Zone.query.order_by(Zone.display_order, Zone.zone_id).all()
        except Exception as e:
            log.warning("Context processor : échec lecture zones_nav : %s", e)
            zones_nav = []
        return {
            "simulation_mode": app.config.get("SIMULATION_MODE", False),
            "sim_speed": app.config.get("SIMULATION_SPEED", 1),
            "weather_profile": app.config.get("WEATHER_PROFILE", "printemps_normal"),
            "zones_nav": zones_nav,
            "garden_name":     app.config.get("GARDEN_NAME", "MonJardin"),
            "garden_location": app.config.get("GARDEN_LOCATION", "Vullierens, Vaud"),
            "garden_owner":    app.config.get("GARDEN_OWNER", "Patrick Pinard"),
            # Cache-buster global pour TOUS les statiques (CSS + JS)
            "static_v": "89",
            # Version applicative (affichée dans la sidebar, login, about)
            "app_version":         "5.0",
            "app_release_date":    "Avril 2026",
        }

    log.info(
        "MonJardin démarré — mode %s",
        "SIMULATION" if app.config.get("SIMULATION_MODE") else "PRODUCTION",
    )
    return app


def _setup_auth(app: Flask) -> None:
    """Intercepte toutes les requêtes : redirige vers /login si auth activée."""
    from flask import request, session, redirect, url_for

    _PUBLIC = {"/login", "/login/post", "/logout"}

    @app.before_request
    def check_auth():
        # Laisser passer les ressources statiques et les routes publiques
        if request.path.startswith("/static"):
            return
        if request.path in _PUBLIC:
            return
        # Vérifier si au moins un utilisateur actif existe
        try:
            from .models import AdminUser
            auth_required = AdminUser.query.filter_by(enabled=True).first() is not None
        except Exception:
            return
        if auth_required and "auth_user" not in session:
            return redirect(f"/login?next={request.path}")


def _migrate_db(app: Flask) -> None:
    """Ajoute les colonnes manquantes sans perdre les données existantes."""
    from sqlalchemy import text, inspect
    with app.app_context():
        inspector = inspect(db.engine)
        with db.engine.connect() as conn:
            # sensor_readings
            sr_cols = {c["name"] for c in inspector.get_columns("sensor_readings")}
            if "temp_serre_c" not in sr_cols:
                conn.execute(text("ALTER TABLE sensor_readings ADD COLUMN temp_serre_c REAL"))
                conn.commit()
                log.info("Migration DB : colonne temp_serre_c ajoutée à sensor_readings")
            # zones
            z_cols = {c["name"] for c in inspector.get_columns("zones")}
            if "length_m" not in z_cols:
                conn.execute(text("ALTER TABLE zones ADD COLUMN length_m REAL DEFAULT 2.0"))
                conn.commit()
                log.info("Migration DB : colonne length_m ajoutée à zones")
            if "width_m" not in z_cols:
                conn.execute(text("ALTER TABLE zones ADD COLUMN width_m REAL DEFAULT 1.0"))
                conn.commit()
                log.info("Migration DB : colonne width_m ajoutée à zones")
            if "display_order" not in z_cols:
                conn.execute(text("ALTER TABLE zones ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0"))
                # Initialise l'ordre par zone_id pour préserver l'affichage actuel
                conn.execute(text("UPDATE zones SET display_order = zone_id WHERE display_order = 0"))
                conn.commit()
                log.info("Migration DB : colonne display_order ajoutée à zones (init = zone_id)")
            # plantings : ordre d'affichage dans la grille visuelle
            p_cols = {c["name"] for c in inspector.get_columns("plantings")}
            if "display_order" not in p_cols:
                conn.execute(text("ALTER TABLE plantings ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0"))
                conn.execute(text("UPDATE plantings SET display_order = id WHERE display_order = 0"))
                conn.commit()
                log.info("Migration DB : colonne display_order ajoutée à plantings (init = id)")
            # plantings : positions dans la grille visuelle (case par case)
            for col, sql in [
                ("grid_row", "ALTER TABLE plantings ADD COLUMN grid_row INTEGER NOT NULL DEFAULT 0"),
                ("grid_col", "ALTER TABLE plantings ADD COLUMN grid_col INTEGER NOT NULL DEFAULT 0"),
                ("grid_w",   "ALTER TABLE plantings ADD COLUMN grid_w   INTEGER NOT NULL DEFAULT 1"),
                ("grid_h",   "ALTER TABLE plantings ADD COLUMN grid_h   INTEGER NOT NULL DEFAULT 1"),
            ]:
                if col not in p_cols:
                    conn.execute(text(sql))
                    conn.commit()
                    log.info("Migration DB : colonne %s ajoutée à plantings", col)
            # Auto-placement des plantings actifs sans position assignée
            _autoplace_plantings_initial()


def _autoplace_plantings_initial() -> None:
    """Place automatiquement les plantings actifs encore en (0,0) sur la grille.

    Appelé une seule fois après migration : remplit la grille de chaque zone
    case par case (row-major) pour préserver l'affichage existant.
    """
    from .models import Planting, Zone
    CELL_CM = 30
    zones = Zone.query.all()
    for z in zones:
        cols = max(4, int((z.length_m or 2.0) * 100 / CELL_CM))
        actives = (Planting.query
                   .filter_by(zone_id=z.zone_id, status="active")
                   .order_by(Planting.id).all())
        # Repérer ceux qui n'ont pas de position (tous en 0,0 et grid_w=1)
        unplaced = [p for p in actives
                    if (p.grid_row or 0) == 0 and (p.grid_col or 0) == 0
                    and (p.grid_w or 1) == 1 and (p.grid_h or 1) == 1]
        # Si le premier planting est aussi en (0,0), considérer tout le set comme à placer
        if not unplaced or (len(unplaced) < len(actives)):
            # Il y a déjà des positions assignées → ne rien faire
            continue
        for idx, p in enumerate(actives):
            p.grid_row = idx // cols
            p.grid_col = idx % cols
            p.grid_w = 1
            p.grid_h = 1
        log.info("Auto-placement initial : zone %s (%d plants)", z.name, len(actives))
    db.session.commit()


def _init_services(app: Flask) -> None:
    """Initialise les singletons de service."""
    from .services.arduino_client import ArduinoClient
    from .services.weather_service import WeatherService
    from .services.planting_advisor import PlantingAdvisor
    from .services.rotation_advisor import RotationAdvisor
    from .services.disease_advisor import DiseaseAdvisor

    sim_mode = app.config.get("SIMULATION_MODE", False)
    weather_sim = None

    if sim_mode:
        # Récupère le simulateur météo déjà démarré dans l'émulateur
        try:
            from simulator.arduino_emulator import get_weather_sim
            weather_sim = get_weather_sim()
            log.debug("Simulateur météo récupéré depuis l'émulateur Arduino")
        except Exception as e:
            log.warning("Émulateur Arduino indisponible (%s) — création d'un simulateur météo autonome", e)
            from simulator.weather_simulator import WeatherSimulator
            weather_sim = WeatherSimulator(profile=app.config.get("WEATHER_PROFILE", "printemps_normal"))

    arduino_url = app.config.get_arduino_api_url() if hasattr(app.config, "get_arduino_api_url") else Config.get_arduino_api_url()

    app.extensions["arduino_client"] = ArduinoClient(
        base_url=arduino_url,
        timeout=app.config.get("ARDUINO_API_TIMEOUT", 5),
    )
    app.extensions["weather_service"] = WeatherService(
        latitude=app.config.get("GARDEN_LATITUDE", 46.778),
        longitude=app.config.get("GARDEN_LONGITUDE", 6.641),
        station_id=app.config.get("METEOSUISSE_STATION_ID", "PAY"),
        simulation_mode=sim_mode,
        weather_simulator=weather_sim,
    )
    app.extensions["planting_advisor"] = PlantingAdvisor(
        plants_db_path=app.config.get("PLANTS_DB_PATH"),
    )

    # Charger plants_db pour le RotationAdvisor (réutilise le contenu déjà lu)
    import json as _json
    from pathlib import Path as _Path
    _plants_db_path = (app.config.get("PLANTS_DB_PATH")
                       or _Path(__file__).parent.parent / "data" / "plants_database.json")
    try:
        with open(_plants_db_path, encoding="utf-8") as f:
            _data = _json.load(f)
            _plants_list = _data if isinstance(_data, list) else _data.get("vegetables", [])
    except Exception:
        _plants_list = []
    app.extensions["rotation_advisor"] = RotationAdvisor(plants_db=_plants_list)
    app.extensions["disease_advisor"]  = DiseaseAdvisor(plants_db=_plants_list)


def _start_scheduler(app: Flask) -> None:
    """Démarre APScheduler avec les deux tâches périodiques."""
    from .services.scheduler import automation_cycle, weather_poll

    speed = app.config.get("SIMULATION_SPEED", 1)
    base_interval = app.config.get("AUTOMATION_INTERVAL", 60)
    # Intervalle effectif : divisé par la vitesse de simulation
    cycle_interval = max(5, int(base_interval / speed))
    weather_interval = max(30, int(1800 / speed))

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=automation_cycle,
        trigger="interval",
        seconds=cycle_interval,
        args=[app],
        id="automation_cycle",
        name="Cycle automatisation jardinage",
        replace_existing=True,
    )
    scheduler.add_job(
        func=weather_poll,
        trigger="interval",
        seconds=weather_interval,
        args=[app],
        id="weather_poll",
        name="Rafraîchissement météo",
        replace_existing=True,
    )
    scheduler.start()
    app.extensions["scheduler"] = scheduler
    log.info(
        "Planificateur démarré : cycle=%ds, météo=%ds (vitesse simulation×%d)",
        cycle_interval, weather_interval, speed,
    )
