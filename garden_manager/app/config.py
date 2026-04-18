"""Configuration de l'application MonJardin."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "monjardin-dev-secret")

    # Mode simulation
    SIMULATION_MODE: bool = os.environ.get("SIMULATION_MODE", "true").lower() == "true"
    SIMULATION_SPEED: int = int(os.environ.get("SIMULATION_SPEED", "1"))
    WEATHER_PROFILE: str = os.environ.get("WEATHER_PROFILE", "printemps_normal")

    # Arduino (réel ou émulateur)
    _emulator_host = os.environ.get("EMULATOR_HOST", "127.0.0.1")
    _emulator_port = os.environ.get("EMULATOR_PORT", "8081")
    _arduino_url = os.environ.get("ARDUINO_API_URL", "http://192.168.1.100:80/api")

    @classmethod
    def get_arduino_api_url(cls) -> str:
        if cls.SIMULATION_MODE:
            return f"http://{cls._emulator_host}:{cls._emulator_port}/api"
        return cls._arduino_url

    ARDUINO_API_TIMEOUT: int = int(os.environ.get("ARDUINO_API_TIMEOUT", "5"))

    # Météo
    GARDEN_LATITUDE: float = float(os.environ.get("GARDEN_LATITUDE", "46.778"))
    GARDEN_LONGITUDE: float = float(os.environ.get("GARDEN_LONGITUDE", "6.641"))
    METEOSUISSE_STATION_ID: str = os.environ.get("METEOSUISSE_STATION_ID", "PAY")

    # Base de données — chemin absolu ou relatif à BASE_DIR
    _db_path = os.environ.get("DATABASE_PATH", "data/garden.db")
    _db_abs = Path(_db_path) if Path(_db_path).is_absolute() else BASE_DIR / _db_path
    SQLALCHEMY_DATABASE_URI: str = f"sqlite:///{_db_abs}"
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "connect_args": {"check_same_thread": False, "timeout": 30},
        "pool_pre_ping": True,
    }

    # Planificateur
    AUTOMATION_INTERVAL: int = int(os.environ.get("AUTOMATION_INTERVAL", "60"))

    # Chemins fichiers de données
    PLANTS_DB_PATH: Path = BASE_DIR / "data" / "plants_database.json"
    CALIBRATION_PATH: Path = BASE_DIR / "data" / "calibration.json"

    # Emulateur
    EMULATOR_HOST: str = os.environ.get("EMULATOR_HOST", "127.0.0.1")
    EMULATOR_PORT: int = int(os.environ.get("EMULATOR_PORT", "8081"))

    # Flask
    FLASK_HOST: str = os.environ.get("FLASK_HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.environ.get("FLASK_PORT", "5000"))
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

    # Email alertes
    SMTP_HOST: str              = os.environ.get("SMTP_HOST", "smtp.bluewin.ch")
    SMTP_PORT: int              = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER: str              = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD: str          = os.environ.get("SMTP_PASSWORD", "")
    MAIL_USE_TLS: bool          = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_DEFAULT_SENDER: str    = os.environ.get("MAIL_DEFAULT_SENDER", os.environ.get("SMTP_USER", ""))
    ADMIN_NOTIFICATION_EMAIL: str = os.environ.get("ADMIN_NOTIFICATION_EMAIL", "ppinard@bluewin.ch")
