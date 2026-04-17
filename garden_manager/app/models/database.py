"""Singleton SQLAlchemy partagé entre tous les modèles."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
