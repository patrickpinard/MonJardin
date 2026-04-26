"""Conseiller détection précoce des maladies du potager.

Analyse les conditions météo récentes/prévues + les plantations actives
pour signaler des risques de maladies fréquentes (mildiou, oïdium, limaces…).

Ne remplace pas l'observation sur le terrain — donne des alertes
contextuelles avec recommandations d'action préventive.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Catalogue des maladies / parasites détectables
# Chaque entrée définit :
#  - target_families : familles botaniques affectées
#  - check(weather, history) → (level, message, action) ou None
# ─────────────────────────────────────────────────────────────────────


def _avg_humidity_high_hours(forecast: list[dict], min_pct: int = 85) -> int:
    """Compte le nombre d'heures consécutives avec humidité air > min_pct."""
    if not forecast:
        return 0
    max_streak = 0
    streak = 0
    for f in forecast:
        # Open-Meteo ne renvoie pas humidité air directement dans notre forecast.
        # Approximation : si pluie ou prob >70% → humidité élevée
        prob = f.get("precip_prob_pct", 0) or 0
        precip = f.get("precip_mm", 0) or 0
        if precip > 0.5 or prob > 70:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def _temp_in_range(forecast: list[dict], t_min: float, t_max: float) -> bool:
    """Vrai si la T° passe dans [t_min, t_max] sur la période."""
    return any(t_min <= (f.get("temperature") or 0) <= t_max for f in forecast)


def _temp_max(forecast: list[dict]) -> float:
    temps = [f.get("temperature") or 0 for f in forecast]
    return max(temps) if temps else 0


def _check_mildiou(weather: dict, forecast: list[dict], plantings_families: set) -> Optional[dict]:
    """Mildiou : T° 15-25°C + humidité air >85% + 4h consécutives.
    Affecte : Solanacées (tomate, pomme de terre), Cucurbitacées."""
    if not (plantings_families & {"Solanacées", "Cucurbitacées"}):
        return None
    in_range = _temp_in_range(forecast or [weather], 15, 25)
    high_hum_hours = _avg_humidity_high_hours(forecast)
    # En conditions actuelles : pluie/forte prob suffit
    cur_humid = (weather.get("precip_prob_pct", 0) or 0) > 70 or (weather.get("precip_mm_6h", 0) or 0) > 1
    if in_range and (high_hum_hours >= 4 or cur_humid):
        affected = []
        if "Solanacées" in plantings_families: affected.append("tomates/pommes de terre")
        if "Cucurbitacées" in plantings_families: affected.append("courgettes/concombres")
        return {
            "id": "mildiou",
            "name": "Mildiou",
            "icon": "🍂",
            "level": "warning",
            "affected": ", ".join(affected),
            "message": f"Conditions favorables au mildiou (T° 15-25°C + humidité élevée).",
            "actions": [
                "Aérer la serre, espacer les plants",
                "Pailler le sol pour éviter les éclaboussures",
                "Pulvériser bouillie bordelaise à titre préventif",
                "Supprimer les feuilles basses des tomates",
            ],
        }
    return None


def _check_oidium(weather: dict, forecast: list[dict], plantings_families: set) -> Optional[dict]:
    """Oïdium : T°>22°C + humidité variable + faible vent.
    Affecte : Cucurbitacées (courgette, concombre, melon), Cucurbits."""
    if not (plantings_families & {"Cucurbitacées"}):
        return None
    t_max = _temp_max(forecast or [weather])
    wind = weather.get("wind_kmh", 0) or 0
    if t_max > 22 and wind < 15:
        return {
            "id": "oidium",
            "name": "Oïdium",
            "icon": "⚪",
            "level": "warning",
            "affected": "courgettes/concombres",
            "message": f"Risque d'oïdium (T° max {t_max:.0f}°C, vent faible).",
            "actions": [
                "Arroser au pied, jamais sur les feuilles",
                "Pulvériser un mélange lait + eau (1:9) en préventif",
                "Couper les feuilles atteintes (taches blanches)",
            ],
        }
    return None


def _check_limaces(weather: dict, forecast: list[dict], plantings_families: set) -> Optional[dict]:
    """Limaces : pluie + douceur (>10°C) après période sèche.
    Affecte : Astéracées (salade), Cucurbitacées, jeunes plants en général."""
    if not plantings_families:
        return None
    cur_t   = weather.get("temperature", 0) or 0
    cur_pr  = (weather.get("precip_prob_pct", 0) or 0)
    cur_mm  = (weather.get("precip_mm_6h", 0) or 0)
    if cur_t > 10 and (cur_mm > 1 or cur_pr > 60):
        return {
            "id": "limaces",
            "name": "Limaces & escargots",
            "icon": "🐌",
            "level": "info",
            "affected": "salades, jeunes plants",
            "message": "Pluie + douceur — sortie nocturne des limaces probable.",
            "actions": [
                "Inspecter le jardin en soirée",
                "Pose de pièges à bière",
                "Cendre de bois ou coquilles d'œuf autour des jeunes plants",
                "Ramassage manuel à la lampe frontale",
            ],
        }
    return None


def _check_gel(weather: dict, forecast: list[dict], plantings_families: set) -> Optional[dict]:
    """Gel : T° < 3°C ou frost_risk déclaré."""
    cur_t = weather.get("temperature", 99) or 99
    frost = weather.get("frost_risk", False)
    forecast_t_min = min((f.get("temperature") or 99) for f in (forecast or [weather]))
    if frost or cur_t < 3 or forecast_t_min < 2:
        return {
            "id": "gel",
            "name": "Gel imminent",
            "icon": "❄️",
            "level": "danger",
            "affected": "plants sensibles non protégés",
            "message": f"Température prévue jusqu'à {forecast_t_min:.1f}°C — risque de gel.",
            "actions": [
                "Couvrir les plants sensibles (voile d'hivernage P30)",
                "Rentrer les jeunes plants en pot",
                "Arroser le sol en soirée (l'humidité protège)",
                "Vannes et lucarne : fermeture automatique active",
            ],
        }
    return None


def _check_canicule(weather: dict, forecast: list[dict], plantings_families: set) -> Optional[dict]:
    """Canicule : T° > 32°C."""
    t_max = _temp_max(forecast or [weather])
    if t_max > 32:
        return {
            "id": "canicule",
            "name": "Canicule",
            "icon": "🌡",
            "level": "warning",
            "affected": "tous les plants",
            "message": f"Pic de chaleur prévu : {t_max:.0f}°C.",
            "actions": [
                "Arroser uniquement le matin tôt ou en soirée",
                "Pailler épais (5-10 cm) pour conserver l'humidité",
                "Installer une toile d'ombrage sur les plants fragiles",
                "Doubler la fréquence d'arrosage des pots",
            ],
        }
    return None


# Liste des checks disponibles
_CHECKS = [
    _check_gel,
    _check_canicule,
    _check_mildiou,
    _check_oidium,
    _check_limaces,
]


class DiseaseAdvisor:
    """Analyse les risques sanitaires du potager."""

    def __init__(self, plants_db: list[dict]) -> None:
        self._family_by_name = {
            p["name"]: p.get("family", "Inconnue") for p in plants_db
        }

    def analyze(self, weather: dict, forecast_24h: list[dict],
                active_plantings: list) -> list[dict]:
        """Retourne la liste des alertes sanitaires actives.

        Triées par gravité : danger > warning > info.
        """
        if not weather:
            return []
        # Familles botaniques actuellement plantées
        families = set()
        for p in active_plantings:
            fam = self._family_by_name.get(p.vegetable_name, "Inconnue")
            if fam != "Inconnue":
                families.add(fam)

        alerts = []
        for check in _CHECKS:
            try:
                result = check(weather, forecast_24h, families)
                if result:
                    alerts.append(result)
            except Exception as e:
                log.warning("Erreur check maladie %s : %s", check.__name__, e)

        # Tri par gravité
        order = {"danger": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda a: order.get(a["level"], 99))
        return alerts
