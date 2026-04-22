"""Destinataires des alertes email avec sélection des types d'alertes."""
import json
from datetime import datetime, timezone
from .database import db

ALERT_TYPES = [
    {"id": "frost",           "label": "Gel nocturne",         "icon": "🌡️", "color": "blue"},
    {"id": "drought",         "label": "Sécheresse critique",  "icon": "💧", "color": "orange"},
    {"id": "sensor_failure",  "label": "Capteur hors service", "icon": "🔌", "color": "red"},
    {"id": "flood",           "label": "Risque inondation",    "icon": "🌊", "color": "blue"},
    {"id": "arduino_offline", "label": "Arduino injoignable",  "icon": "📡", "color": "red"},
    {"id": "harvest",         "label": "Récolte imminente",    "icon": "🌾", "color": "green"},
]
ALERT_TYPE_IDS = [a["id"] for a in ALERT_TYPES]


class AlertRecipient(db.Model):
    __tablename__ = "alert_recipients"

    id               = db.Column(db.Integer, primary_key=True)
    email            = db.Column(db.String(120), unique=True, nullable=False)
    name             = db.Column(db.String(80), nullable=True)
    enabled          = db.Column(db.Boolean, default=True, nullable=False)
    alert_types_json = db.Column(db.Text, default=lambda: json.dumps(ALERT_TYPE_IDS))
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    @property
    def alert_types(self) -> list:
        try:
            return json.loads(self.alert_types_json or "[]")
        except Exception:
            return list(ALERT_TYPE_IDS)

    @alert_types.setter
    def alert_types(self, value: list):
        self.alert_types_json = json.dumps([v for v in value if v in ALERT_TYPE_IDS])

    def has_alert(self, alert_id: str) -> bool:
        return alert_id in self.alert_types

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "email":       self.email,
            "name":        self.name or "",
            "enabled":     self.enabled,
            "alert_types": self.alert_types,
        }
