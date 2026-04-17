"""Client HTTP vers l'Arduino Edge Control (réel ou émulateur)."""
import logging
from typing import Optional

import requests

log = logging.getLogger(__name__)


class ArduinoClient:
    """Abstraction matérielle — même code en simulation et en production."""

    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._consecutive_failures: int = 0
        self._last_error: Optional[str] = None

    def _get(self, path: str) -> Optional[dict]:
        try:
            resp = requests.get(f"{self._base_url}{path}", timeout=self._timeout)
            resp.raise_for_status()
            self._consecutive_failures = 0
            return resp.json()
        except Exception as e:
            self._consecutive_failures += 1
            self._last_error = str(e)
            log.warning("Arduino GET %s échoué (%d): %s", path, self._consecutive_failures, e)
            return None

    def _post(self, path: str, payload: dict) -> bool:
        try:
            resp = requests.post(
                f"{self._base_url}{path}",
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            self._consecutive_failures = 0
            return data.get("ok", True)
        except Exception as e:
            self._consecutive_failures += 1
            self._last_error = str(e)
            log.warning("Arduino POST %s échoué (%d): %s", path, self._consecutive_failures, e)
            return False

    def get_all_sensors(self) -> Optional[dict]:
        return self._get("/sensors")

    def get_zone_sensor(self, zone_id: int) -> Optional[dict]:
        return self._get(f"/sensors/{zone_id}")

    def get_actuator_status(self) -> Optional[dict]:
        return self._get("/actuators/status")

    def set_valve(self, zone_id: int, state: str) -> bool:
        return self._post(f"/actuators/valve/{zone_id}", {"state": state})

    def set_roof(self, state: str) -> bool:
        return self._post("/actuators/roof", {"state": state})

    def get_health(self) -> Optional[dict]:
        return self._get("/health")

    @property
    def is_reachable(self) -> bool:
        return self._consecutive_failures == 0

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures
