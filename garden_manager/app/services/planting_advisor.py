"""Conseiller de plantation : compagnonnage, saisonnalité, compatibilité."""
import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class PlantingAdvisor:
    """Charge la base de données légumes et fournit des conseils."""

    def __init__(self, plants_db_path: Path) -> None:
        try:
            with open(plants_db_path, encoding="utf-8") as f:
                data = json.load(f)
            self._plants: list[dict] = data.get("vegetables", [])
            self._rules: dict = data.get("companion_rules", {})
        except Exception as e:
            log.error("Impossible de charger la base légumes : %s", e)
            self._plants = []
            self._rules = {}
        self._index: dict[str, dict] = {p["name"]: p for p in self._plants}

    def get_all_vegetables(self) -> list[dict]:
        return self._plants

    def get_vegetable(self, name: str) -> Optional[dict]:
        return self._index.get(name)

    def get_companions(self, vegetable_name: str) -> dict:
        veg = self._index.get(vegetable_name)
        if not veg:
            return {"good": [], "bad": [], "notes": ""}
        return {
            "good": veg.get("companions", []),
            "bad": veg.get("bad_companions", []),
            "notes": veg.get("notes_fr", ""),
        }

    def get_planting_advice(self, zone_id: int, current_month: int) -> list[dict]:
        """Légumes recommandés pour le mois courant dans la zone."""
        try:
            from ..models import Planting
            active_names = {
                p.vegetable_name
                for p in Planting.query.filter_by(zone_id=zone_id, status="active").all()
            }
        except Exception as e:
            log.warning("Échec lecture plantings actifs zone %d : %s", zone_id, e)
            active_names = set()

        advice = []
        for veg in self._plants:
            months = veg.get("planting_months_ch", [])
            if current_month not in months:
                continue
            if veg["name"] in active_names:
                continue
            advice.append({
                "name": veg["name"],
                "water_need": veg.get("water_need", "medium"),
                "sun_need": veg.get("sun_need", "full"),
                "notes_fr": veg.get("notes_fr", ""),
                "harvest_months": veg.get("harvest_months_ch", []),
            })
        return advice

    def check_zone_compatibility(self, zone_id: int) -> list[str]:
        """Vérifie la compatibilité entre légumes actifs d'une zone.

        Retourne une liste d'avertissements en français.
        """
        try:
            from ..models import Planting
            active = [
                p.vegetable_name
                for p in Planting.query.filter_by(zone_id=zone_id, status="active").all()
            ]
        except Exception as e:
            log.warning("Échec lecture plantings pour compatibilité zone %d : %s", zone_id, e)
            return []

        warnings = []
        checked: set[tuple[str, str]] = set()
        for veg_name in active:
            veg = self._index.get(veg_name)
            if not veg:
                continue
            for bad in veg.get("bad_companions", []):
                if bad in active:
                    pair = tuple(sorted([veg_name, bad]))
                    if pair not in checked:
                        checked.add(pair)
                        warnings.append(
                            f"⚠️ {veg_name} et {bad} sont incompatibles (mauvais voisinage)"
                        )
        return warnings

    def get_golden_associations(self) -> list[dict]:
        return self._rules.get("golden_associations", [])

    def get_harvest_forecast(self, zone_id: int, days: int = 14) -> list[dict]:
        """Légumes à récolter dans les N prochains jours."""
        from datetime import date, timedelta
        try:
            from ..models import Planting
            today = date.today()
            horizon = today + timedelta(days=days)
            plantings = Planting.query.filter_by(zone_id=zone_id, status="active").all()
        except Exception as e:
            log.warning("Échec lecture plantings pour prévision récolte zone %d : %s", zone_id, e)
            return []

        upcoming = []
        for p in plantings:
            if p.expected_harvest_date and today <= p.expected_harvest_date <= horizon:
                days_left = (p.expected_harvest_date - today).days
                upcoming.append({
                    "vegetable_name": p.vegetable_name,
                    "expected_harvest_date": p.expected_harvest_date.isoformat(),
                    "days_left": days_left,
                })
        return sorted(upcoming, key=lambda x: x["days_left"])
