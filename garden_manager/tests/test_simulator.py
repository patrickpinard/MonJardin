"""Test d'intégration : simulateur sur 24h accélérées."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from simulator.sensor_simulator import SensorSimulator
from simulator.actuator_simulator import ActuatorSimulator
from simulator.weather_simulator import WeatherSimulator


class TestSensorSimulator:

    def test_initial_moisture_in_range(self):
        sim = SensorSimulator(speed=1.0)
        snap = sim.snapshot()
        for zone in snap["zones"]:
            assert 5.0 <= zone["soil_moisture_pct"] <= 98.0

    def test_temperature_reasonable(self):
        sim = SensorSimulator(speed=1.0)
        sim.tick()
        snap = sim.snapshot()
        # Température doit être dans une plage réaliste pour Yverdon
        assert -15.0 <= snap["temperature_c"] <= 45.0

    def test_valve_increases_moisture(self):
        sim = SensorSimulator(speed=360.0)  # 360× accéléré
        initial_moisture = sim._moisture[1]
        # Ouvrir vanne zone 1
        sim.set_valve(1, True)
        # Simuler 10 minutes (avec vitesse ×360 = 3600s simulés)
        for _ in range(100):
            sim.tick()
            time.sleep(0.01)
        final_moisture = sim._moisture[1]
        assert final_moisture > initial_moisture, (
            f"Humidité devrait avoir augmenté : {initial_moisture:.1f}% → {final_moisture:.1f}%"
        )

    def test_moisture_stays_in_bounds(self):
        """Humidité ne dépasse jamais 0-100% après 500 ticks."""
        sim = SensorSimulator(speed=60.0)
        for _ in range(500):
            sim.tick()
            time.sleep(0.001)
        snap = sim.snapshot()
        for zone in snap["zones"]:
            assert 5.0 <= zone["soil_moisture_pct"] <= 98.0

    def test_offline_sensor_excluded(self):
        sim = SensorSimulator()
        sim.set_offline_sensors({2, 3})
        snap = sim.snapshot()
        zone_ids = [z["zone_id"] for z in snap["zones"]]
        assert 2 not in zone_ids
        assert 3 not in zone_ids
        assert 1 in zone_ids
        assert 4 in zone_ids

    def test_roof_effect_on_evaporation(self):
        """Toit ouvert augmente l'évaporation zone 1 si T > 28°C.
        On fixe l'heure à 20h (pic ete_chaud ~34°C) pour garantir T > seuil."""
        import time as _time
        import datetime as dt_mod
        from unittest.mock import patch

        # Fixer l'heure à 20h — T = 26 + 8*sin(0) + T_amp→ pic → ~34°C
        fixed_dt = dt_mod.datetime(2026, 7, 17, 20, 0)

        def run_evap(roof_open: bool, ticks: int = 300) -> float:
            # Chaque tick : 0.01s réel × speed=360 = 3.6s simulés
            call_count = [0]
            def fake_mono():
                v = 10000.0 + call_count[0] * 0.01
                call_count[0] += 1
                return v

            with patch("simulator.sensor_simulator.datetime") as mock_dt, \
                 patch("simulator.sensor_simulator.MOISTURE_NOISE", 0.0), \
                 patch("simulator.sensor_simulator.time") as mock_time:
                mock_dt.datetime.now.return_value = fixed_dt
                mock_time.monotonic.side_effect = fake_mono
                sim = SensorSimulator(speed=360.0, weather_profile="ete_chaud")
                sim._moisture = {1: 70.0, 2: 70.0, 3: 70.0, 4: 70.0}
                sim.set_roof(roof_open)
                for _ in range(ticks):
                    sim.tick()
            return sim._moisture[1]

        moisture_roof_open = run_evap(roof_open=True)
        moisture_roof_closed = run_evap(roof_open=False)
        assert moisture_roof_open < moisture_roof_closed, (
            f"Toit ouvert={moisture_roof_open:.1f}% devrait être < toit fermé={moisture_roof_closed:.1f}%"
        )


class TestWeatherSimulator:

    def test_all_profiles_return_data(self):
        from simulator.weather_simulator import PROFILES
        for profile_name in PROFILES:
            ws = WeatherSimulator(profile=profile_name)
            cond = ws.get_current_conditions()
            assert "temperature" in cond
            assert "frost_risk" in cond
            assert "source" in cond

    def test_frost_profile_has_frost_risk(self):
        ws = WeatherSimulator(profile="gel_tardif")
        # Tester à 3h du matin (heure de gel probable)
        from unittest.mock import patch
        import datetime
        mock_dt = datetime.datetime(2026, 4, 17, 3, 0)
        with patch("simulator.weather_simulator.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            mock_datetime.utcnow.return_value = mock_dt
            # Répéter pour avoir de la variance
            frost_seen = any(
                WeatherSimulator(profile="gel_tardif").get_current_conditions()["frost_risk"]
                for _ in range(30)
            )
        # Avec frost_prob=0.4, on devrait voir au moins 1 gel en 30 essais
        # (probabilité d'échec = 0.6^30 ≈ 0.0001%)
        assert frost_seen

    def test_forecast_48h_length(self):
        ws = WeatherSimulator()
        forecast = ws.get_48h_forecast()
        assert len(forecast) == 48

    def test_canicule_no_frost(self):
        ws = WeatherSimulator(profile="canicule")
        for _ in range(20):
            cond = ws.get_current_conditions()
            assert not cond["frost_risk"]

    def test_list_profiles(self):
        profiles = WeatherSimulator.list_profiles()
        assert len(profiles) == 6


class TestActuatorSimulator:

    def test_valve_open_close(self):
        sensor_sim = SensorSimulator()
        act_sim = ActuatorSimulator(sensor_sim)
        result = act_sim.set_valve(1, "open")
        assert result["ok"]
        status = act_sim.get_all_status()
        valve1 = next(v for v in status["valves"] if v["zone_id"] == 1)
        assert valve1["state"] == "open"

    def test_stuck_valve_returns_error(self):
        sensor_sim = SensorSimulator()
        act_sim = ActuatorSimulator(sensor_sim)
        act_sim.inject_stuck_valve(2)
        result = act_sim.set_valve(2, "open")
        assert not result["ok"]
        assert "bloquée" in result["error"]

    def test_invalid_zone_returns_error(self):
        sensor_sim = SensorSimulator()
        act_sim = ActuatorSimulator(sensor_sim)
        result = act_sim.set_valve(99, "open")
        assert not result["ok"]

    def test_reset_closes_all(self):
        sensor_sim = SensorSimulator()
        act_sim = ActuatorSimulator(sensor_sim)
        act_sim.set_valve(1, "open")
        act_sim.set_valve(3, "open")
        act_sim.reset()
        status = act_sim.get_all_status()
        for v in status["valves"]:
            assert v["state"] == "close"
