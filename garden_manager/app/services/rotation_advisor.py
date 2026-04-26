"""Conseiller de rotation des cultures.

Vérifie l'historique de plantation par zone (toutes les Plantings, actives
ou archivées), détecte les conflits de famille botanique et suggère le
meilleur emplacement pour une nouvelle plantation.

Règle d'or : ne pas replanter la même famille au même endroit avant
**3 ans minimum** (idéalement). Tolérance acceptée : 12 mois (warning).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

log = logging.getLogger(__name__)

# Période minimale recommandée avant de replanter la même famille (jours)
ROTATION_MIN_DAYS = 365 * 3   # 3 ans (idéal)
ROTATION_WARNING_DAYS = 365   # 1 an (tolérance, warning uniquement)


class RotationAdvisor:
    """Calcule les recommandations de rotation selon l'historique."""

    def __init__(self, plants_db: list[dict]) -> None:
        # Index nom de légume → famille botanique
        self._family_by_name: dict[str, str] = {
            p["name"]: p.get("family", "Inconnue") for p in plants_db
        }

    def family_of(self, vegetable_name: str) -> str:
        return self._family_by_name.get(vegetable_name, "Inconnue")

    def get_zone_history(self, plantings, zone_id: int, max_days: int = 365 * 3) -> list[dict]:
        """Retourne l'historique des plantations d'une zone (max_days en arrière).

        Liste triée par date la plus récente en premier.
        """
        cutoff = date.today() - timedelta(days=max_days)
        history = []
        for p in plantings:
            if p.zone_id != zone_id:
                continue
            ref_date = p.planted_date or p.expected_harvest_date
            if ref_date is None or ref_date < cutoff:
                continue
            history.append({
                "vegetable_name": p.vegetable_name,
                "family":         self.family_of(p.vegetable_name),
                "planted_date":   p.planted_date,
                "harvest_date":   p.expected_harvest_date,
                "status":         p.status,
                "days_ago":       (date.today() - ref_date).days,
            })
        history.sort(key=lambda h: h["days_ago"])
        return history

    def check_conflict(self, plantings, zone_id: int, vegetable_name: str) -> Optional[dict]:
        """Vérifie si planter ce légume dans cette zone pose un conflit de rotation.

        Retourne :
        - None si aucun conflit
        - {"level": "warning", "family", "previous", "days_ago", "message"}
          si conflit (légume de la même famille planté dans les 3 ans)
        """
        target_family = self.family_of(vegetable_name)
        if target_family == "Inconnue":
            return None

        history = self.get_zone_history(plantings, zone_id, max_days=ROTATION_MIN_DAYS)
        # Trouver le plus récent de la même famille (en excluant cette espèce
        # exacte, déjà gérée par espace_row dans la zone)
        conflict = None
        for h in history:
            if h["family"] != target_family:
                continue
            if conflict is None or h["days_ago"] < conflict["days_ago"]:
                conflict = h

        if not conflict:
            return None

        days = conflict["days_ago"]
        prev_name = conflict["vegetable_name"]
        if days < ROTATION_WARNING_DAYS:
            level = "danger"
            msg = (f"⚠️ Famille des {target_family} déjà cultivée ici il y a "
                   f"{days} jour{'s' if days > 1 else ''} ({prev_name}) — "
                   f"rotation insuffisante (idéal : 3 ans).")
        else:
            level = "warning"
            years = round(days / 365, 1)
            msg = (f"⚠️ Famille des {target_family} cultivée ici il y a "
                   f"{years} an{'s' if years > 1 else ''} ({prev_name}) — "
                   f"attendre 3 ans pour rotation idéale.")

        return {
            "level":       level,
            "family":      target_family,
            "previous":    prev_name,
            "days_ago":    days,
            "message":     msg,
        }

    def suggest_best_zone(self, plantings, zones: list, vegetable_name: str) -> Optional[dict]:
        """Suggère la meilleure zone pour planter ce légume.

        Critères de score (plus haut = mieux) :
        - +100 si jamais planté de cette famille dans cette zone
        - +X selon ancienneté de la dernière plantation de la même famille
        - -1000 si planté dans les 12 derniers mois (rotation insuffisante)
        """
        target_family = self.family_of(vegetable_name)
        if target_family == "Inconnue" or not zones:
            return None

        scored = []
        for z in zones:
            history = self.get_zone_history(plantings, z.zone_id, max_days=ROTATION_MIN_DAYS)
            same_family = [h for h in history if h["family"] == target_family]
            if not same_family:
                score = 100  # jamais planté → idéal
                reason = f"Jamais cultivé de {target_family} ici"
            else:
                most_recent = min(h["days_ago"] for h in same_family)
                if most_recent < ROTATION_WARNING_DAYS:
                    score = -1000 + most_recent
                    reason = f"Famille des {target_family} cultivée il y a {most_recent}j"
                else:
                    # Plus c'est ancien, mieux c'est
                    score = most_recent  # 365..1095
                    years = round(most_recent / 365, 1)
                    reason = f"Famille des {target_family} il y a {years}an"
            scored.append({
                "zone": z,
                "score": score,
                "reason": reason,
            })
        scored.sort(key=lambda s: s["score"], reverse=True)
        best = scored[0]
        return {
            "zone_id":   best["zone"].zone_id,
            "zone_name": best["zone"].name,
            "score":     best["score"],
            "reason":    best["reason"],
            "is_safe":   best["score"] >= 0,
        }

    def get_zone_rotation_history_by_year(
        self, plantings, zone_id: int, years: int = 3
    ) -> dict[int, list[dict]]:
        """Retourne l'historique d'une zone groupé par année (pour la vue Plan rotation).

        Format : {2024: [{"family": "Solanacées", "names": ["Tomate", "Poivron"]}, ...]}
        """
        today = date.today()
        result: dict[int, dict[str, set]] = {}
        for y_offset in range(years):
            year = today.year - y_offset
            result[year] = {}

        cutoff = today - timedelta(days=365 * years)
        for p in plantings:
            if p.zone_id != zone_id:
                continue
            ref_date = p.planted_date or p.expected_harvest_date
            if ref_date is None or ref_date < cutoff:
                continue
            year = ref_date.year
            if year not in result:
                continue
            family = self.family_of(p.vegetable_name)
            result[year].setdefault(family, set()).add(p.vegetable_name)

        # Convertir en liste de dicts triée
        out: dict[int, list[dict]] = {}
        for year, fam_map in result.items():
            out[year] = [
                {"family": f, "names": sorted(list(names))}
                for f, names in sorted(fam_map.items())
            ]
        return out
