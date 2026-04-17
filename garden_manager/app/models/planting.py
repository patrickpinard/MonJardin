"""Modèles pour les plantations et le cache météo."""
from datetime import datetime
from .database import db


class Planting(db.Model):
    __tablename__ = "plantings"

    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, nullable=False, index=True)
    vegetable_name = db.Column(db.String(64), nullable=False)
    variety = db.Column(db.String(64), nullable=True)
    planted_date = db.Column(db.Date, nullable=True)
    expected_harvest_date = db.Column(db.Date, nullable=True)
    water_need = db.Column(db.String(8), default="medium")  # low | medium | high
    status = db.Column(db.String(16), default="active")  # planned | active | harvested | removed
    notes = db.Column(db.Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "zone_id": self.zone_id,
            "vegetable_name": self.vegetable_name,
            "variety": self.variety,
            "planted_date": self.planted_date.isoformat() if self.planted_date else None,
            "expected_harvest_date": self.expected_harvest_date.isoformat() if self.expected_harvest_date else None,
            "water_need": self.water_need,
            "status": self.status,
            "notes": self.notes,
        }


class WeatherCache(db.Model):
    __tablename__ = "weather_cache"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    forecast_json = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(32), default="meteosuisse")
    valid_until = db.Column(db.DateTime, nullable=True)
