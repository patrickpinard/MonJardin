#!/usr/bin/env python3
"""Point d'entrée MonJardin — démarre l'émulateur (si simulation) puis Flask."""
import logging
import os
import sys
import time
import threading

from dotenv import load_dotenv

# Charger .env en premier, avant tout import de config
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("monjardin")

# Ajouter le répertoire parent au chemin pour les imports relatifs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SIMULATION_MODE = os.environ.get("SIMULATION_MODE", "true").lower() == "true"
EMULATOR_HOST = os.environ.get("EMULATOR_HOST", "127.0.0.1")
EMULATOR_PORT = int(os.environ.get("EMULATOR_PORT", "8081"))
SIMULATION_SPEED = float(os.environ.get("SIMULATION_SPEED", "1"))
WEATHER_PROFILE = os.environ.get("WEATHER_PROFILE", "printemps_normal")
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))


def _start_emulator() -> None:
    """Démarre l'émulateur Arduino dans un thread daemon."""
    from simulator.arduino_emulator import start_emulator
    start_emulator(
        host=EMULATOR_HOST,
        port=EMULATOR_PORT,
        speed=SIMULATION_SPEED,
        weather_profile=WEATHER_PROFILE,
    )


def _wait_for_emulator(timeout: float = 10.0) -> bool:
    """Attend que l'émulateur soit prêt à répondre."""
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"http://{EMULATOR_HOST}:{EMULATOR_PORT}/api/health", timeout=1)
            if resp.status_code == 200:
                log.info("Émulateur Arduino prêt sur http://%s:%d", EMULATOR_HOST, EMULATOR_PORT)
                return True
        except Exception:
            pass
        time.sleep(0.3)
    log.error("Émulateur Arduino non disponible après %.0fs", timeout)
    return False


def main() -> None:
    if SIMULATION_MODE:
        log.info("Mode SIMULATION (vitesse ×%g, profil : %s)", SIMULATION_SPEED, WEATHER_PROFILE)
        t = threading.Thread(target=_start_emulator, daemon=True, name="arduino-emulator")
        t.start()
        _wait_for_emulator()
    else:
        log.info("Mode PRODUCTION — Arduino sur %s", os.environ.get("ARDUINO_API_URL"))

    from app import create_app
    app = create_app()

    log.info("Dashboard disponible sur http://localhost:%d", FLASK_PORT)
    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true",
        use_reloader=False,  # Désactivé pour éviter double démarrage du scheduler
    )


if __name__ == "__main__":
    main()
