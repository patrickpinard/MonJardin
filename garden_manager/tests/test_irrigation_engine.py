"""Tests unitaires du moteur de décision d'irrigation."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from unittest.mock import patch

from app.services.irrigation_engine import evaluate_zone, IrrigationDecision


def _zone(mode="auto", low=30.0, high=65.0):
    from unittest.mock import MagicMock
    z = MagicMock()
    z.zone_id = 2
    z.name = "Soleil"
    z.irrigation_mode = mode
    z.moisture_threshold_low = low
    z.moisture_threshold_high = high
    z.irrigation_duration_min = 15
    return z


def _weather(frost=False, precip_mm=0.0, precip_prob=10.0, wind=10.0, temp=18.0):
    return {
        "frost_risk": frost,
        "precip_mm_6h": precip_mm,
        "precip_prob_pct": precip_prob,
        "wind_kmh": wind,
        "temperature": temp,
    }


def _now(hour=8):
    return datetime(2026, 4, 17, hour, 0, 0)


# Patch _get_max_water_need pour éviter les appels DB
def _no_db(monkeypatch):
    monkeypatch.setattr(
        "app.services.irrigation_engine._get_max_water_need",
        lambda z: "medium",
    )


class TestIrrigationEngine:

    def test_disabled_mode(self):
        zone = _zone(mode="disabled")
        dec = evaluate_zone(zone, 20.0, 18.0, _weather(), _now())
        assert dec.action == "skip"
        assert "désactivée" in dec.reason

    def test_manual_mode(self):
        zone = _zone(mode="manual")
        dec = evaluate_zone(zone, 20.0, 18.0, _weather(), _now())
        assert dec.action == "skip"
        assert "manuel" in dec.reason

    def test_frost_closes_valve(self):
        zone = _zone()
        dec = evaluate_zone(zone, 50.0, 2.0, _weather(frost=True), _now())
        assert dec.action == "close"
        assert dec.trigger_type == "frost"

    def test_frost_temperature_threshold(self):
        zone = _zone()
        dec = evaluate_zone(zone, 50.0, 2.5, _weather(), _now())
        assert dec.action == "close"
        assert "gel" in dec.reason.lower()

    def test_rain_postpones_watering(self):
        zone = _zone()
        dec = evaluate_zone(zone, 20.0, 18.0, _weather(precip_mm=6.0), _now())
        assert dec.action == "skip"
        assert dec.trigger_type == "weather"
        assert "pluie" in dec.reason.lower()

    def test_heatwave_outside_window_skips(self):
        zone = _zone()
        # 14h, canicule à 35°C, hors fenêtre 20-22h
        dec = evaluate_zone(zone, 20.0, 35.0, _weather(), _now(hour=14))
        assert dec.action == "skip"
        assert dec.trigger_type == "heatwave"

    def test_heatwave_at_20h_allows_watering(self):
        zone = _zone()
        with patch("app.services.irrigation_engine._get_max_water_need", return_value="medium"):
            # 20h, canicule, humidité basse → doit arroser
            dec = evaluate_zone(zone, 20.0, 35.0, _weather(), _now(hour=20))
        assert dec.action == "open"

    def test_low_moisture_triggers_open(self):
        zone = _zone()
        with patch("app.services.irrigation_engine._get_max_water_need", return_value="medium"):
            dec = evaluate_zone(zone, 25.0, 18.0, _weather(), _now(hour=7))
        assert dec.action == "open"
        assert dec.trigger_type == "auto"
        assert "25.0%" in dec.reason

    def test_high_moisture_triggers_close(self):
        zone = _zone()
        dec = evaluate_zone(zone, 70.0, 18.0, _weather(), _now())
        assert dec.action == "close"
        assert "70.0%" in dec.reason

    def test_normal_moisture_skips(self):
        zone = _zone()
        with patch("app.services.irrigation_engine._get_max_water_need", return_value="medium"):
            dec = evaluate_zone(zone, 50.0, 18.0, _weather(), _now())
        assert dec.action == "skip"

    def test_high_water_need_lowers_effective_threshold(self):
        """Légume gourmand → seuil bas augmente de 20%."""
        zone = _zone(low=30.0)
        with patch("app.services.irrigation_engine._get_max_water_need", return_value="high"):
            # Humidité 34% : > 30% mais < 36% (30*1.2) → doit arroser
            dec = evaluate_zone(zone, 34.0, 18.0, _weather(), _now(hour=7))
        assert dec.action == "open"

    def test_low_water_need_raises_effective_threshold(self):
        """Plante économe → seuil bas réduit de 20%."""
        zone = _zone(low=30.0)
        with patch("app.services.irrigation_engine._get_max_water_need", return_value="low"):
            # Humidité 26% : > 24% (30*0.8) → ne pas arroser
            dec = evaluate_zone(zone, 26.0, 18.0, _weather(), _now(hour=7))
        assert dec.action == "skip"

    def test_outside_preferred_window_still_waters(self):
        """Hors créneau optimal, l'arrosage se fait quand même."""
        zone = _zone()
        with patch("app.services.irrigation_engine._get_max_water_need", return_value="medium"):
            dec = evaluate_zone(zone, 20.0, 18.0, _weather(), _now(hour=14))
        assert dec.action == "open"
        assert "hors créneau" in dec.reason
