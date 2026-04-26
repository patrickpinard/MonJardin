"""Modèle pour les photos prises dans une zone (PWA mobile)."""
from datetime import datetime, timezone
from .database import db


class ZonePhoto(db.Model):
    __tablename__ = "zone_photos"

    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, nullable=False, index=True)
    filename = db.Column(db.String(128), nullable=False)  # nom unique sur disque (UUID + ext)
    captured_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
                            nullable=False, index=True)
    caption = db.Column(db.String(200), nullable=True)
    file_size_kb = db.Column(db.Integer, nullable=True)
    width  = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "zone_id": self.zone_id,
            "filename": self.filename,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "caption": self.caption,
            "file_size_kb": self.file_size_kb,
            "width": self.width,
            "height": self.height,
        }

    def __repr__(self) -> str:
        return f"<ZonePhoto z{self.zone_id}/{self.filename}>"
