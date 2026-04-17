"""Tests unitaires du moteur de décision toit serre."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from app.services.roof_engine import evaluate_roof


def _weather(frost=False, precip_mm=0.0, precip_prob=10.0, wind=10.0):
    return {
        "frost_risk": frost,
        "precip_mm_6h": precip_mm,
        "precip_prob_pct": precip_prob,
        "wind_kmh": wind,
    }


def _now(hour=14, month=6):
    return datetime(2026, month, 17, hour, 0, 0)


class TestRoofEngine:

    def test_frost_closes_roof(self):
        dec = evaluate_roof(50.0, 2.0, _weather(frost=True), _now(), "open")
        assert dec.action == "close"
        assert dec.trigger_type == "temperature"

    def test_low_temp_closes_roof(self):
        dec = evaluate_roof(50.0, 6.0, _weather(), _now(), "open")
        assert dec.action == "close"

    def test_rain_probability_closes_roof(self):
        dec = evaluate_roof(50.0, 18.0, _weather(precip_prob=60.0), _now(), "open")
        assert dec.action == "close"
        assert dec.trigger_type == "weather"

    def test_precip_mm_closes_roof(self):
        dec = evaluate_roof(50.0, 20.0, _weather(precip_mm=1.0), _now(), "open")
        assert dec.action == "close"

    def test_high_wind_closes_roof(self):
        dec = evaluate_roof(50.0, 22.0, _weather(wind=45.0), _now(), "open")
        assert dec.action == "close"

    def test_nighttime_cold_month_closes(self):
        # Octobre, 22h → fermeture nocturne
        dec = evaluate_roof(50.0, 10.0, _weather(), _now(hour=22, month=10), "open")
        assert dec.action == "close"

    def test_summer_night_no_close(self):
        # Juillet, 22h → pas de fermeture nocturne (mois chaud)
        dec = evaluate_roof(50.0, 15.0, _weather(), _now(hour=22, month=7), "close")
        # La température est 15°C > 8°C, pas de pluie, pas de vent → maintain ou open
        assert dec.action in ("open", "maintain")

    def test_high_temp_opens_roof(self):
        dec = evaluate_roof(50.0, 26.0, _weather(), _now(), "close")
        assert dec.action == "open"
        assert "25" in dec.reason

    def test_high_moisture_opens_roof(self):
        dec = evaluate_roof(80.0, 22.0, _weather(), _now(), "close")
        assert dec.action == "open"
        assert "ventilation" in dec.reason.lower()

    def test_normal_conditions_maintain(self):
        dec = evaluate_roof(50.0, 18.0, _weather(), _now(), "close")
        assert dec.action == "maintain"

    def test_default_is_closed(self):
        """Le toit reste fermé en l'absence de raison d'ouvrir."""
        dec = evaluate_roof(50.0, 10.0, _weather(), _now(hour=3), "close")
        assert dec.action in ("close", "maintain")
