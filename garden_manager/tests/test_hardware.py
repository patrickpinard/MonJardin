"""Tests d'intégration matérielle — Arduino Edge Control réel.

Usage :
    pytest tests/test_hardware.py -m hardware -v

Prérequis :
    - Arduino allumé et accessible sur le réseau
    - Variable ARDUINO_API_URL définie dans .env ou l'environnement
      ex. : ARDUINO_API_URL=http://192.168.1.100:80/api

Ces tests vérifient que l'API Arduino respecte exactement le contrat
attendu par le reste du système (ArduinoClient, routes_api.py, etc.).
"""
import os
import time
import pytest
import requests

# ── Configuration ────────────────────────────────────────────────────────────
_raw_url = os.getenv("ARDUINO_API_URL", "http://192.168.1.100:80/api")
BASE = _raw_url.rstrip("/")
if not BASE.endswith("/api"):
    BASE = BASE.rstrip("/") + "/api"
TIMEOUT = 5
pytestmark = pytest.mark.hardware


# ── Fixture : skip si Arduino inaccessible ───────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def require_arduino():
    """Skip tout le module si l'Arduino n'est pas joignable."""
    try:
        r = requests.get(f"{BASE}/health", timeout=TIMEOUT)
        if r.status_code != 200:
            pytest.skip(f"Arduino répond HTTP {r.status_code} — tests ignorés")
    except requests.RequestException as exc:
        pytest.skip(f"Arduino non joignable ({exc}) — tests ignorés")


@pytest.fixture(scope="module")
def session():
    """Session HTTP réutilisable pour le module."""
    s = requests.Session()
    yield s
    s.close()


# ── Health ───────────────────────────────────────────────────────────────────
class TestArduinoHealth:

    def test_status_ok(self, session):
        r = session.get(f"{BASE}/health", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d.get("status") in ("ok", "degraded")

    def test_uptime_positive(self, session):
        r = session.get(f"{BASE}/health", timeout=TIMEOUT)
        d = r.json()
        assert "uptime_s" in d
        assert isinstance(d["uptime_s"], int)
        assert d["uptime_s"] >= 0

    def test_content_type_json(self, session):
        r = session.get(f"{BASE}/health", timeout=TIMEOUT)
        assert "application/json" in r.headers.get("Content-Type", "")


# ── Capteurs ─────────────────────────────────────────────────────────────────
class TestArduinoSensors:

    def test_all_sensors_returns_zones(self, session):
        r = session.get(f"{BASE}/sensors", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert "zones" in d
        assert isinstance(d["zones"], list)
        assert len(d["zones"]) >= 1

    def test_temperature_realistic(self, session):
        r = session.get(f"{BASE}/sensors", timeout=TIMEOUT)
        d = r.json()
        assert "temperature_c" in d
        assert -20.0 <= d["temperature_c"] <= 60.0

    def test_zone_schema(self, session):
        """Chaque zone doit avoir les champs attendus par ArduinoClient."""
        r = session.get(f"{BASE}/sensors", timeout=TIMEOUT)
        for zone in r.json()["zones"]:
            assert "zone_id" in zone
            assert zone["zone_id"] in range(1, 5)
            assert "soil_moisture_pct" in zone
            assert 0.0 <= zone["soil_moisture_pct"] <= 100.0
            assert "raw_adc" in zone
            assert 0 <= zone["raw_adc"] <= 4095

    def test_individual_zone_1(self, session):
        r = session.get(f"{BASE}/sensors/1", timeout=TIMEOUT)
        # 200 si zone 1 existe, 404 si pas de capteur dans cette zone
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            d = r.json()
            assert d.get("zone_id") == 1

    def test_sensors_consistent_across_calls(self, session):
        """Deux lectures successives donnent des humidités cohérentes (±15%)."""
        r1 = session.get(f"{BASE}/sensors", timeout=TIMEOUT).json()
        time.sleep(1)
        r2 = session.get(f"{BASE}/sensors", timeout=TIMEOUT).json()
        z1_a = {z["zone_id"]: z["soil_moisture_pct"] for z in r1["zones"]}
        z1_b = {z["zone_id"]: z["soil_moisture_pct"] for z in r2["zones"]}
        for zid in z1_a:
            if zid in z1_b:
                diff = abs(z1_a[zid] - z1_b[zid])
                assert diff < 15.0, f"Zone {zid} : variation trop grande {diff:.1f}% en 1 s"


# ── Actionneurs ──────────────────────────────────────────────────────────────
class TestArduinoActuators:

    def test_get_actuator_status(self, session):
        r = session.get(f"{BASE}/actuators/status", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert "valves" in d
        for v in d["valves"]:
            assert "zone_id" in v
            assert "state" in v
            assert v["state"] in ("open", "close", "unknown")

    def test_roof_state_present(self, session):
        r = session.get(f"{BASE}/actuators/status", timeout=TIMEOUT)
        d = r.json()
        assert "roof_state" in d or "roof" in d

    def test_valve_open_close_cycle_zone1(self, session):
        """Ouvre puis ferme la vanne zone 1 — vérifie l'état après chaque commande."""
        # Ouvrir
        r = session.post(f"{BASE}/actuators/valve/1",
                         json={"action": "open"}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        time.sleep(2)
        status = session.get(f"{BASE}/actuators/status", timeout=TIMEOUT).json()
        v1 = next((v for v in status["valves"] if v["zone_id"] == 1), None)
        if v1:
            assert v1["state"] == "open", f"Vanne 1 attendue 'open', reçu '{v1['state']}'"

        # Fermer
        r = session.post(f"{BASE}/actuators/valve/1",
                         json={"action": "close"}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        time.sleep(2)
        status = session.get(f"{BASE}/actuators/status", timeout=TIMEOUT).json()
        v1 = next((v for v in status["valves"] if v["zone_id"] == 1), None)
        if v1:
            assert v1["state"] == "close"

    def test_invalid_valve_zone_rejected(self, session):
        """Zone 99 n'existe pas — doit retourner ok=False ou HTTP 4xx."""
        r = session.post(f"{BASE}/actuators/valve/99",
                         json={"action": "open"}, timeout=TIMEOUT)
        if r.status_code == 200:
            assert not r.json().get("ok")
        else:
            assert r.status_code in (400, 404)

    def test_roof_close(self, session):
        """Ferme le toit de la serre — opération sûre."""
        r = session.post(f"{BASE}/actuators/roof",
                         json={"action": "close"}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ── Connexion continue ───────────────────────────────────────────────────────
class TestArduinoConnectionMonitor:
    """Fiabilité de la connexion : latence et stabilité sur N requêtes."""

    def test_latency_under_500ms(self, session):
        """Latence moyenne < 500 ms sur réseau local."""
        latencies = []
        for _ in range(5):
            t0 = time.perf_counter()
            session.get(f"{BASE}/health", timeout=TIMEOUT)
            latencies.append((time.perf_counter() - t0) * 1000)
        avg = sum(latencies) / len(latencies)
        assert avg < 500, f"Latence moyenne {avg:.0f} ms dépasse 500 ms"

    def test_10_consecutive_reads_no_error(self, session):
        """10 lectures de /sensors consécutives sans erreur ni timeout."""
        errors = 0
        for _ in range(10):
            try:
                r = session.get(f"{BASE}/sensors", timeout=TIMEOUT)
                if r.status_code != 200:
                    errors += 1
            except requests.RequestException:
                errors += 1
        assert errors == 0, f"{errors}/10 lectures ont échoué"

    def test_reconnect_after_delay(self, session):
        """L'Arduino répond toujours correctement après 5 s d'inactivité."""
        time.sleep(5)
        r = session.get(f"{BASE}/health", timeout=TIMEOUT)
        assert r.status_code == 200
