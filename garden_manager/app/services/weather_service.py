"""Service météo avec fallback : MétéoSuisse → Open-Meteo → simulateur."""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

log = logging.getLogger(__name__)

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"
METEOSUISSE_URL = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/VQHA80.json"
CACHE_DURATION_MIN = 30


class WeatherService:
    """Fournit les données météo avec fallback automatique."""

    def __init__(self, latitude: float, longitude: float,
                 station_id: str = "PAY",
                 simulation_mode: bool = False,
                 weather_simulator=None) -> None:
        self._lat = latitude
        self._lon = longitude
        self._station_id = station_id
        self._simulation_mode = simulation_mode
        self._weather_sim = weather_simulator
        self._cache: Optional[dict] = None
        self._cache_until: Optional[datetime] = None

    def get_current(self) -> dict:
        """Retourne les conditions actuelles (avec cache 30 min)."""
        if self._cache and self._cache_until and datetime.now(timezone.utc).replace(tzinfo=None) < self._cache_until:
            cached = dict(self._cache)
            cached["source"] = cached.get("source", "cache") + " (cache)"
            return cached

        if self._simulation_mode and self._weather_sim:
            data = self._weather_sim.get_current_conditions()
            self._set_cache(data)
            return data

        # Essai MétéoSuisse
        try:
            data = self._fetch_meteosuisse()
            self._set_cache(data)
            return data
        except Exception as e:
            log.warning("MétéoSuisse indisponible: %s", e)

        # Fallback Open-Meteo
        try:
            data = self._fetch_openmeteo()
            self._set_cache(data)
            return data
        except Exception as e:
            log.warning("Open-Meteo indisponible: %s", e)

        # Cache expiré utilisé quand même
        if self._cache:
            log.warning("Utilisation du cache météo expiré.")
            return self._cache

        # Données par défaut
        return self._default_conditions()

    def get_forecast_48h(self) -> list[dict]:
        """Retourne les prévisions sur 48h."""
        if self._simulation_mode and self._weather_sim:
            return self._weather_sim.get_48h_forecast()
        try:
            return self._fetch_openmeteo_forecast()
        except Exception as e:
            log.warning("Prévisions 48h indisponibles: %s", e)
            if self._weather_sim:
                return self._weather_sim.get_48h_forecast()
            return []

    def _fetch_meteosuisse(self) -> dict:
        resp = requests.get(METEOSUISSE_URL, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        station = next(
            (s for s in raw.get("features", []) if s.get("id") == self._station_id),
            None,
        )
        if not station:
            raise ValueError(f"Station {self._station_id} non trouvée")
        props = station.get("properties", {})
        temp = props.get("TT_10MIN", props.get("tre200s0"))
        wind = props.get("FF_10MIN", props.get("fkl010z0"))
        precip = props.get("RRR_10MIN", props.get("rre150z0"))
        return {
            "temperature": float(temp) if temp is not None else 15.0,
            "precip_prob_pct": 0.0,
            "precip_mm_6h": float(precip) * 6 if precip is not None else 0.0,
            "wind_kmh": float(wind) * 3.6 if wind is not None else 10.0,
            "frost_risk": float(temp) < 3.0 if temp is not None else False,
            "source": "meteosuisse",
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }

    def _fetch_openmeteo(self) -> dict:
        params = {
            "latitude": self._lat,
            "longitude": self._lon,
            "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m",
            "forecast_days": 1,
            "timezone": "Europe/Zurich",
        }
        resp = requests.get(OPENMETEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        hourly = data.get("hourly", {})
        # Prendre la première heure disponible
        temps = hourly.get("temperature_2m", [15.0])
        precip_prob = hourly.get("precipitation_probability", [0])
        precip = hourly.get("precipitation", [0.0])
        wind = hourly.get("wind_speed_10m", [10.0])
        temp = float(temps[0]) if temps else 15.0
        return {
            "temperature": temp,
            "precip_prob_pct": float(precip_prob[0]) if precip_prob else 0.0,
            "precip_mm_6h": sum(float(p) for p in precip[:6]) if precip else 0.0,
            "wind_kmh": float(wind[0]) if wind else 10.0,
            "frost_risk": temp < 3.0,
            "source": "openmeteo",
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }

    def _fetch_openmeteo_forecast(self) -> list[dict]:
        params = {
            "latitude": self._lat,
            "longitude": self._lon,
            "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m",
            "forecast_days": 2,
            "timezone": "Europe/Zurich",
        }
        resp = requests.get(OPENMETEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        probs = hourly.get("precipitation_probability", [])
        precips = hourly.get("precipitation", [])
        winds = hourly.get("wind_speed_10m", [])
        forecast = []
        for i, t in enumerate(times[:48]):
            temp = float(temps[i]) if i < len(temps) else 15.0
            forecast.append({
                "hour": t,
                "temperature": temp,
                "precip_prob_pct": float(probs[i]) if i < len(probs) else 0.0,
                "precip_mm": float(precips[i]) if i < len(precips) else 0.0,
                "wind_kmh": float(winds[i]) if i < len(winds) else 10.0,
                "frost_risk": temp < 3.0,
            })
        return forecast

    def _set_cache(self, data: dict) -> None:
        self._cache = data
        self._cache_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=CACHE_DURATION_MIN)

    @staticmethod
    def _default_conditions() -> dict:
        return {
            "temperature": 15.0,
            "precip_prob_pct": 0.0,
            "precip_mm_6h": 0.0,
            "wind_kmh": 10.0,
            "frost_risk": False,
            "source": "default",
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
