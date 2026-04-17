"""Simulateur physique des capteurs du jardin (4 zones)."""
import datetime
import math
import random
import time
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Température de base pour Vullierens (°C)
T_BASE = 18.0
# Amplitude sinusoïdale jour/nuit
T_AMP_DAY = 8.0
# Température serre : offset au-dessus de l'extérieur (effet de serre)
T_SERRE_OFFSET_BASE = 5.0   # +5°C de base
T_SERRE_OFFSET_SUN  = 8.0   # +8°C supplémentaires en plein soleil (14h)
T_SERRE_NOISE = 0.3
# Bruit gaussien température (écart-type)
T_NOISE = 0.25
# Bruit humidité (écart-type)
MOISTURE_NOISE = 0.04
# Taux d'évaporation par zone (%/seconde — drain naturel)
DRAIN_RATES: dict[int, float] = {1: 0.00028, 2: 0.00050, 3: 0.00039, 4: 0.00069}
# Taux d'humidification quand vanne ouverte (%/seconde)
WATER_RATE = 0.040
# Augmentation d'évaporation si toit ouvert et T > seuil (facteur multiplicatif)
ROOF_EVAP_FACTOR = 1.30
ROOF_EVAP_TEMP_THRESHOLD = 28.0
# Humidités initiales par zone (%)
INITIAL_MOISTURE: dict[int, float] = {1: 62.0, 2: 70.0, 3: 55.0, 4: 42.0}

# Profils météo : ajustement du drain selon conditions
WEATHER_DRAIN_MULTIPLIERS: dict[str, float] = {
    "printemps_normal": 1.0,
    "ete_chaud": 1.5,
    "ete_orageux": 0.8,
    "automne_humide": 0.6,
    "gel_tardif": 0.4,
    "canicule": 2.0,
}


class SensorSimulator:
    """Simule les capteurs de 4 zones avec physique réaliste."""

    def __init__(self, speed: float = 1.0, weather_profile: str = "printemps_normal") -> None:
        self._speed = max(1.0, float(speed))
        self._weather_profile = weather_profile
        self._moisture: dict[int, float] = dict(INITIAL_MOISTURE)
        self._temperature_c: float = T_BASE
        self._temp_serre_c: float = T_BASE + T_SERRE_OFFSET_BASE
        self._valve_open: dict[int, bool] = {z: False for z in range(1, 5)}
        self._roof_open: bool = False
        self._last_tick: float = time.monotonic()
        self._offline_sensors: set[int] = set()
        self._start_time: float = time.time()

    def tick(self) -> None:
        """Avance la simulation selon le temps écoulé × vitesse."""
        now = time.monotonic()
        real_dt = now - self._last_tick
        self._last_tick = now
        # Temps simulé (en secondes)
        dt = min(real_dt * self._speed, 300.0)

        # Heure simulée (on utilise l'heure réelle pour que le cycle jour/nuit soit naturel)
        _now = datetime.datetime.now()
        hour = _now.hour + _now.minute / 60.0

        # Température sinusoïdale (pic à 14h)
        self._temperature_c = (
            T_BASE + T_AMP_DAY * math.sin((hour - 14.0) * math.pi / 12.0)
            + random.gauss(0, T_NOISE)
        )
        self._temperature_c = round(self._temperature_c, 2)

        # Température serre (DS18B20 #2) : extérieur + offset soleil + bruit
        sun_boost = T_SERRE_OFFSET_SUN * max(0.0, math.sin((hour - 14.0) * math.pi / 12.0))
        roof_factor = 0.5 if self._roof_open else 1.0  # toit ouvert = moins d'effet de serre
        self._temp_serre_c = round(
            self._temperature_c + (T_SERRE_OFFSET_BASE + sun_boost) * roof_factor
            + random.gauss(0, T_SERRE_NOISE), 2
        )

        drain_mult = WEATHER_DRAIN_MULTIPLIERS.get(self._weather_profile, 1.0)
        # Facteur chaleur supplémentaire
        heat_factor = 1.0 + max(0.0, (self._temperature_c - 20.0) / 20.0)

        for z in range(1, 5):
            drain = DRAIN_RATES[z] * dt * drain_mult * heat_factor

            # Toit ouvert accélère l'évaporation zone 1 si chaud
            if z == 1 and self._roof_open and self._temperature_c > ROOF_EVAP_TEMP_THRESHOLD:
                drain *= ROOF_EVAP_FACTOR

            self._moisture[z] -= drain

            # Arrosage
            if self._valve_open[z]:
                self._moisture[z] += WATER_RATE * dt

            # Bruit
            self._moisture[z] += random.gauss(0, MOISTURE_NOISE)
            self._moisture[z] = max(5.0, min(98.0, self._moisture[z]))

    def snapshot(self) -> dict:
        """Retourne l'état courant au format API Arduino."""
        zones = []
        for z in range(1, 5):
            if z in self._offline_sensors:
                continue
            zones.append({
                "zone_id": z,
                "soil_moisture_pct": round(self._moisture[z], 2),
                "raw_adc": int(self._moisture[z] / 100.0 * 4095),
            })
        return {
            "temperature_c": self._temperature_c,
            "temp_serre_c": self._temp_serre_c,
            "zones": zones,
        }

    def set_valve(self, zone_id: int, open_valve: bool) -> None:
        if zone_id in range(1, 5):
            self._valve_open[zone_id] = open_valve

    def set_roof(self, open_roof: bool) -> None:
        self._roof_open = open_roof

    def get_uptime_s(self) -> int:
        return int(time.time() - self._start_time)

    def set_offline_sensors(self, zones: set[int]) -> None:
        self._offline_sensors = zones

    def set_weather_profile(self, profile: str) -> None:
        if profile in WEATHER_DRAIN_MULTIPLIERS:
            self._weather_profile = profile
