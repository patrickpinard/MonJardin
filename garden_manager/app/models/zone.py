"""Modèle de configuration des zones de jardinage."""
from datetime import datetime
from .database import db


class Zone(db.Model):
    __tablename__ = "zones"

    zone_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    has_roof = db.Column(db.Boolean, default=False)   # True = serre vitrée
    irrigation_mode = db.Column(db.String(16), default="auto")  # auto | manual | disabled
    moisture_threshold_low = db.Column(db.Float, default=30.0)
    moisture_threshold_high = db.Column(db.Float, default=65.0)
    irrigation_duration_min = db.Column(db.Integer, default=15)
    length_m = db.Column(db.Float, default=2.0)
    width_m  = db.Column(db.Float, default=1.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def area_m2(self) -> float:
        return round((self.length_m or 2.0) * (self.width_m or 1.0), 2)

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "description": self.description,
            "has_roof": self.has_roof,
            "irrigation_mode": self.irrigation_mode,
            "moisture_threshold_low": self.moisture_threshold_low,
            "moisture_threshold_high": self.moisture_threshold_high,
            "irrigation_duration_min": self.irrigation_duration_min,
            "length_m": self.length_m or 2.0,
            "width_m": self.width_m or 1.0,
        }

    def __repr__(self) -> str:
        return f"<Zone {self.zone_id}: {self.name}>"
