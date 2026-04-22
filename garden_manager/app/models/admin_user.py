"""Modèle utilisateur pour l'authentification admin (username + PIN)."""
import hashlib
from datetime import datetime, timezone
from .database import db


class AdminUser(db.Model):
    __tablename__ = "admin_users"

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(64), unique=True, nullable=False)
    pin_hash   = db.Column(db.String(64), nullable=False)
    enabled    = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    last_login = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def hash_pin(pin: str) -> str:
        return hashlib.sha256(pin.strip().encode()).hexdigest()

    def check_pin(self, pin: str) -> bool:
        return self.pin_hash == self.hash_pin(pin)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "username":   self.username,
            "enabled":    self.enabled,
            "created_at": self.created_at.strftime("%d.%m.%Y") if self.created_at else None,
            "last_login": self.last_login.strftime("%d.%m.%Y %H:%M") if self.last_login else None,
        }
