"""Simulateur d'état des actionneurs (vannes + vérin toit)."""
import time
import logging
from typing import Optional
from .sensor_simulator import SensorSimulator

log = logging.getLogger(__name__)

# Durée simulée du mouvement du vérin (secondes)
ACTUATOR_MOVE_DURATION_S = 30


class ActuatorSimulator:
    """Maintient l'état mutable des vannes et du vérin."""

    def __init__(self, sensor_sim: SensorSimulator) -> None:
        self._sensor_sim = sensor_sim
        # État des vannes : zone_id → "open" | "close"
        self._valve_states: dict[int, str] = {z: "close" for z in range(1, 5)}
        # État du toit
        self._roof_state: str = "close"  # sécurité : fermé par défaut
        self._roof_moving_since: Optional[float] = None
        self._roof_target: Optional[str] = None
        # Injections de pannes
        self._stuck_valve: Optional[int] = None
        self._wifi_loss: bool = False

    def set_valve(self, zone_id: int, state: str) -> dict:
        """Ouvre ou ferme la vanne d'une zone."""
        if zone_id not in range(1, 5):
            return {"ok": False, "error": f"Zone {zone_id} invalide"}
        if self._stuck_valve == zone_id:
            log.warning("Vanne zone %d bloquée (injection panne).", zone_id)
            return {"ok": False, "error": f"Vanne zone {zone_id} bloquée"}
        self._valve_states[zone_id] = state
        self._sensor_sim.set_valve(zone_id, state == "open")
        log.info("Vanne zone %d : %s", zone_id, state)
        return {"ok": True, "zone_id": zone_id, "state": state}

    def set_roof(self, state: str) -> dict:
        """Lance le mouvement du toit vers l'état cible."""
        if state not in ("open", "close"):
            return {"ok": False, "error": "État invalide"}
        if self._roof_state == state and self._roof_moving_since is None:
            return {"ok": True, "roof_state": state, "message": "Déjà dans cet état"}
        self._roof_target = state
        self._roof_moving_since = time.monotonic()
        log.info("Toit : démarrage mouvement vers %s", state)
        return {"ok": True, "roof_state": "moving", "target": state}

    def update_roof(self) -> None:
        """Vérifie si le vérin a terminé son mouvement."""
        if self._roof_moving_since is None:
            return
        elapsed = time.monotonic() - self._roof_moving_since
        if elapsed >= ACTUATOR_MOVE_DURATION_S:
            self._roof_state = self._roof_target or self._roof_state
            self._roof_moving_since = None
            self._roof_target = None
            self._sensor_sim.set_roof(self._roof_state == "open")
            log.info("Toit : mouvement terminé → %s", self._roof_state)

    def get_all_status(self) -> dict:
        """Retourne l'état de tous les actionneurs."""
        self.update_roof()
        moving = self._roof_moving_since is not None
        roof_display = "moving" if moving else self._roof_state
        return {
            "valves": [
                {"zone_id": z, "state": self._valve_states[z]}
                for z in range(1, 5)
            ],
            "roof_state": roof_display,
            # Cible du mouvement (None si pas en mouvement)
            "roof_target": self._roof_target if moving else None,
        }

    def inject_stuck_valve(self, zone_id: Optional[int]) -> None:
        self._stuck_valve = zone_id

    def inject_wifi_loss(self, active: bool) -> None:
        self._wifi_loss = active

    def reset(self) -> None:
        """Réinitialise tous les états."""
        for z in range(1, 5):
            self._valve_states[z] = "close"
            self._sensor_sim.set_valve(z, False)
        self._roof_state = "close"
        self._roof_moving_since = None
        self._roof_target = None
        self._sensor_sim.set_roof(False)
        self._stuck_valve = None
        self._wifi_loss = False
