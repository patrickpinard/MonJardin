"""Modèle pour les relevés capteurs."""
from datetime import datetime, timezone
from .database import db


class SensorReading(db.Model):
    __tablename__ = "sensor_readings"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
    zone_id = db.Column(db.Integer, nullable=False, index=True)
    soil_moisture_pct = db.Column(db.Float, nullable=True)
    raw_adc = db.Column(db.Float, nullable=True)
    temperature_c = db.Column(db.Float, nullable=True)
    temp_serre_c = db.Column(db.Float, nullable=True)
    is_simulated = db.Column(db.Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "zone_id": self.zone_id,
            "soil_moisture_pct": self.soil_moisture_pct,
            "raw_adc": self.raw_adc,
            "temperature_c": self.temperature_c,
            "temp_serre_c": self.temp_serre_c,
            "is_simulated": self.is_simulated,
        }

    def __repr__(self) -> str:
        return f"<SensorReading zone={self.zone_id} moisture={self.soil_moisture_pct:.1f}% @{self.timestamp}>"
