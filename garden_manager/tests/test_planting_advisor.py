"""Tests unitaires du conseiller de plantation."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from app.services.planting_advisor import PlantingAdvisor

PLANTS_DB = Path(__file__).parent.parent / "data" / "plants_database.json"


class TestPlantingAdvisor:
    @classmethod
    def setup_class(cls):
        cls.advisor = PlantingAdvisor(PLANTS_DB)

    def test_loads_vegetables(self):
        vegs = self.advisor.get_all_vegetables()
        assert len(vegs) >= 15

    def test_get_vegetable_by_name(self):
        veg = self.advisor.get_vegetable("Tomate")
        assert veg is not None
        assert veg["water_need"] == "high"

    def test_unknown_vegetable_returns_none(self):
        assert self.advisor.get_vegetable("Choucroute") is None

    def test_companions_tomate(self):
        info = self.advisor.get_companions("Tomate")
        assert "Basilic" in info["good"]
        assert "Fenouil" in info["bad"]

    def test_planting_advice_april(self):
        # En avril, Carotte et Salade devraient être suggérées
        from unittest.mock import patch, MagicMock
        with patch("app.models.Planting") as mock_planting:
            mock_planting.query.filter_by.return_value.all.return_value = []
            advice = self.advisor.get_planting_advice(zone_id=2, current_month=4)
        names = [v["name"] for v in advice]
        assert "Carotte" in names
        assert "Salade" in names

    def test_planting_advice_excludes_active(self):
        """Un légume déjà actif dans la zone ne doit pas être suggéré."""
        from unittest.mock import MagicMock, patch
        mock_p = MagicMock()
        mock_p.vegetable_name = "Carotte"
        # Patch app.models.Planting (le nom re-exporté utilisé par le lazy import)
        with patch("app.models.Planting") as mock_planting:
            mock_planting.query.filter_by.return_value.all.return_value = [mock_p]
            advice = self.advisor.get_planting_advice(zone_id=2, current_month=4)
        names = [v["name"] for v in advice]
        assert "Carotte" not in names

    def test_compatibility_tomate_chou_warning(self):
        """Tomate + Chou → avertissement incompatibilité (Chou est dans bad_companions de Tomate)."""
        from unittest.mock import MagicMock, patch
        # Les deux légumes sont dans la DB avec incompatibilité mutuelle
        plantings = [MagicMock(vegetable_name="Tomate"), MagicMock(vegetable_name="Chou")]
        with patch("app.models.Planting") as mock_planting:
            mock_planting.query.filter_by.return_value.all.return_value = plantings
            warnings = self.advisor.check_zone_compatibility(zone_id=1)
        assert len(warnings) > 0
        combined = " ".join(warnings)
        assert "Tomate" in combined or "Chou" in combined

    def test_no_compatibility_warnings_for_good_pair(self):
        """Tomate + Basilic → pas d'avertissement."""
        from unittest.mock import MagicMock, patch
        plantings = [MagicMock(vegetable_name="Tomate"), MagicMock(vegetable_name="Basilic")]
        with patch("app.models.Planting") as mock_planting:
            mock_planting.query.filter_by.return_value.all.return_value = plantings
            warnings = self.advisor.check_zone_compatibility(zone_id=1)
        assert warnings == []

    def test_golden_associations_present(self):
        golden = self.advisor.get_golden_associations()
        assert len(golden) >= 3
