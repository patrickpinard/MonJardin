"""Exports des modèles SQLAlchemy."""
from .database import db
from .sensor_data import SensorReading
from .zone import Zone
from .irrigation_log import IrrigationLog, RoofLog, JournalEntry
from .planting import Planting, WeatherCache
from .admin_user import AdminUser
from .alert_recipient import AlertRecipient, ALERT_TYPES, ALERT_TYPE_IDS

__all__ = [
    "db",
    "SensorReading",
    "Zone",
    "IrrigationLog",
    "RoofLog",
    "JournalEntry",
    "Planting",
    "WeatherCache",
    "AdminUser",
    "AlertRecipient",
    "ALERT_TYPES",
    "ALERT_TYPE_IDS",
]
