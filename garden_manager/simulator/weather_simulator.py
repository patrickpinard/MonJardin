"""Simulateur météo pour Yverdon — 6 profils prédéfinis."""
import math
import random
from datetime import datetime, timedelta
from typing import Any

# Paramètres des profils météo
PROFILES: dict[str, dict[str, Any]] = {
    "printemps_normal": {
        "t_base": 14.0, "t_amp": 7.0,
        "precip_prob_day": 0.25, "precip_max_mm": 5.0,
        "wind_base": 10.0, "wind_gust_max": 30.0,
        "frost_prob_night": 0.05,
        "label": "Printemps normal",
    },
    "ete_chaud": {
        "t_base": 26.0, "t_amp": 8.0,
        "precip_prob_day": 0.05, "precip_max_mm": 1.0,
        "wind_base": 8.0, "wind_gust_max": 20.0,
        "frost_prob_night": 0.0,
        "label": "Été chaud",
    },
    "ete_orageux": {
        "t_base": 24.0, "t_amp": 7.0,
        "precip_prob_day": 0.40, "precip_max_mm": 20.0,
        "wind_base": 15.0, "wind_gust_max": 55.0,
        "frost_prob_night": 0.0,
        "label": "Été orageux",
    },
    "automne_humide": {
        "t_base": 10.0, "t_amp": 5.0,
        "precip_prob_day": 0.55, "precip_max_mm": 8.0,
        "wind_base": 20.0, "wind_gust_max": 45.0,
        "frost_prob_night": 0.10,
        "label": "Automne humide",
    },
    "gel_tardif": {
        "t_base": 4.0, "t_amp": 6.0,
        "precip_prob_day": 0.20, "precip_max_mm": 3.0,
        "wind_base": 8.0, "wind_gust_max": 20.0,
        "frost_prob_night": 0.40,
        "label": "Gel tardif (Saints de Glace)",
    },
    "canicule": {
        "t_base": 34.0, "t_amp": 6.0,
        "precip_prob_day": 0.02, "precip_max_mm": 0.5,
        "wind_base": 5.0, "wind_gust_max": 15.0,
        "frost_prob_night": 0.0,
        "label": "Canicule",
    },
}


class WeatherSimulator:
    """Génère des données météo réalistes pour Yverdon selon un profil."""

    def __init__(self, profile: str = "printemps_normal") -> None:
        self._profile_name = profile if profile in PROFILES else "printemps_normal"
        self._p = PROFILES[self._profile_name]

    def set_profile(self, profile: str) -> None:
        if profile in PROFILES:
            self._profile_name = profile
            self._p = PROFILES[profile]

    def get_current_conditions(self) -> dict:
        """Retourne les conditions actuelles simulées."""
        hour = datetime.now().hour
        p = self._p
        temp = p["t_base"] + p["t_amp"] * math.sin((hour - 14) * math.pi / 12)
        temp += random.gauss(0, 0.5)

        # Pluie : plus probable l'après-midi pour les orages d'été
        is_afternoon = 13 <= hour <= 18
        precip_prob = p["precip_prob_day"] * (1.5 if is_afternoon and "orageux" in self._profile_name else 1.0)
        has_precip = random.random() < precip_prob
        precip_mm_6h = random.uniform(0.5, p["precip_max_mm"]) if has_precip else 0.0

        wind = p["wind_base"] + random.uniform(0, p["wind_gust_max"] * 0.3)
        wind += random.gauss(0, 2.0)
        wind = max(0.0, wind)

        # Gel : uniquement la nuit (entre 22h et 6h)
        is_night = hour >= 22 or hour <= 6
        frost_risk = is_night and random.random() < p["frost_prob_night"]
        if frost_risk:
            temp = min(temp, 2.0)

        return {
            "temperature": round(temp, 1),
            "precip_prob_pct": round(precip_prob * 100, 1),
            "precip_mm_6h": round(precip_mm_6h, 1),
            "wind_kmh": round(wind, 1),
            "frost_risk": frost_risk,
            "source": "simulator",
            "profile": self._profile_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_48h_forecast(self) -> list[dict]:
        """Génère 48 heures de prévisions horaires cohérentes."""
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        forecast = []
        p = self._p
        for i in range(48):
            ts = now + timedelta(hours=i)
            hour = ts.hour
            temp = p["t_base"] + p["t_amp"] * math.sin((hour - 14) * math.pi / 12)
            temp += random.gauss(0, 0.8)
            is_night = hour >= 22 or hour <= 6
            frost = is_night and random.random() < p["frost_prob_night"]
            if frost:
                temp = min(temp, 2.0)
            precip_prob = p["precip_prob_day"] * 100
            precip = random.uniform(0, p["precip_max_mm"]) if random.random() < p["precip_prob_day"] else 0.0
            wind = max(0.0, p["wind_base"] + random.gauss(0, 3.0))
            forecast.append({
                "hour": ts.isoformat(),
                "temperature": round(temp, 1),
                "precip_prob_pct": round(precip_prob, 0),
                "precip_mm": round(precip, 1),
                "wind_kmh": round(wind, 1),
                "frost_risk": frost,
            })
        return forecast

    @staticmethod
    def list_profiles() -> list[dict]:
        return [{"id": k, "label": v["label"]} for k, v in PROFILES.items()]
