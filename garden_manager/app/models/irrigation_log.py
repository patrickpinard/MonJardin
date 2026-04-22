"""Modèles pour les journaux d'irrigation et du toit."""
from datetime import datetime, timezone
from .database import db


class IrrigationLog(db.Model):
    __tablename__ = "irrigation_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
    zone_id = db.Column(db.Integer, nullable=False, index=True)
    action = db.Column(db.String(8), nullable=False)  # open | close
    trigger_type = db.Column(db.String(16), nullable=True)  # auto | manual | schedule | weather | frost | heatwave
    reason = db.Column(db.Text, nullable=True)
    moisture_at_trigger = db.Column(db.Float, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "zone_id": self.zone_id,
            "action": self.action,
            "trigger_type": self.trigger_type,
            "reason": self.reason,
            "moisture_at_trigger": self.moisture_at_trigger,
            "duration_seconds": self.duration_seconds,
        }


class RoofLog(db.Model):
    __tablename__ = "roof_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
    action = db.Column(db.String(8), nullable=False)  # open | close
    trigger_type = db.Column(db.String(16), nullable=True)  # auto | manual | weather | temperature
    reason = db.Column(db.Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "action": self.action,
            "trigger_type": self.trigger_type,
            "reason": self.reason,
        }


class JournalEntry(db.Model):
    """Journal de toutes les décisions et événements système."""
    __tablename__ = "journal_entries"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
    level = db.Column(db.String(8), default="info", index=True)  # info | warning | error | danger
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)  # JSON optionnel

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "level": self.level,
            "message": self.message,
            "details": self.details,
        }
