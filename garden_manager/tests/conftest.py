"""Fixtures pytest partagées."""
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_arduino_client():
    """Client Arduino simulé retournant des données capteurs figées."""
    client = MagicMock()
    client.get_all_sensors.return_value = {
        "temperature_c": 18.5,
        "zones": [
            {"zone_id": 1, "soil_moisture_pct": 42.0, "raw_adc": 1720},
            {"zone_id": 2, "soil_moisture_pct": 65.0, "raw_adc": 2665},
            {"zone_id": 3, "soil_moisture_pct": 28.0, "raw_adc": 1147},
            {"zone_id": 4, "soil_moisture_pct": 55.0, "raw_adc": 2252},
        ],
    }
    client.get_actuator_status.return_value = {
        "valves": [{"zone_id": i, "state": "close"} for i in range(1, 5)],
        "roof_state": "close",
    }
    client.set_valve.return_value = True
    client.set_roof.return_value = True
    client.get_health.return_value = {"status": "ok", "simulated": True}
    client.is_reachable = True
    client.consecutive_failures = 0
    return client


@pytest.fixture
def sample_zone():
    """Zone de test avec configuration par défaut."""
    zone = MagicMock()
    zone.zone_id = 2
    zone.name = "Soleil"
    zone.irrigation_mode = "auto"
    zone.moisture_threshold_low = 30.0
    zone.moisture_threshold_high = 65.0
    zone.irrigation_duration_min = 15
    return zone


@pytest.fixture
def sample_weather():
    """Conditions météo normales."""
    return {
        "temperature": 18.0,
        "precip_prob_pct": 10.0,
        "precip_mm_6h": 0.0,
        "wind_kmh": 12.0,
        "frost_risk": False,
        "source": "test",
    }
