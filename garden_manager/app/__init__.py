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
        # Création des tables
        db.create_all()
        # Données initiales
        from .seed import ensure_defaults, seed_demo_history
        ensure_defaults(app)
        if app.config.get("SIMULATION_MODE", False):
            seed_demo_history(app)

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

    # Contexte global pour les templates
    @app.context_processor
    def inject_globals():
        from .models import Zone
        try:
            zones_nav = Zone.query.order_by(Zone.zone_id).all()
        except Exception:
            zones_nav = []
        return {
            "simulation_mode": app.config.get("SIMULATION_MODE", False),
            "sim_speed": app.config.get("SIMULATION_SPEED", 1),
            "zones_nav": zones_nav,
        }

    log.info(
        "MonJardin démarré — mode %s",
        "SIMULATION" if app.config.get("SIMULATION_MODE") else "PRODUCTION",
    )
    return app


def _init_services(app: Flask) -> None:
    """Initialise les singletons de service."""
    from .services.arduino_client import ArduinoClient
    from .services.weather_service import WeatherService
    from .services.planting_advisor import PlantingAdvisor

    sim_mode = app.config.get("SIMULATION_MODE", False)
    weather_sim = None

    if sim_mode:
        # Récupère le simulateur météo déjà démarré dans l'émulateur
        try:
            from simulator.arduino_emulator import get_weather_sim
            weather_sim = get_weather_sim()
        except Exception:
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
