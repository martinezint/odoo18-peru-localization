# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.ple_9_1_activos import (
    PLE_ACTIVOS_COLUMNS,
    Ple9_1Generator,
    Ple9_1Line,
    render_line,
)


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle9_1Render(TransactionCase):
    def _line(self, **overrides):
        defaults = {
            "period": "20261200",
            "cuo": 1,
            "correlativo": "A00000001",
            "account_code": "3361",
            "asset_code": "AF001",
            "asset_name": "Laptop Dell",
            "brand": "Dell",
            "model": "Latitude 5530",
            "serial": "ABC123",
            "acquisition_date": date(2025, 1, 15),
            "start_date": date(2025, 2, 1),
            "useful_life_years": 4,
            "depreciation_rate": Decimal("25"),
            "historical_value": Decimal("4000.00"),
            "accumulated_prev": Decimal("0"),
            "depreciation_year": Decimal("1000.00"),
            "accumulated_close": Decimal("1000.00"),
        }
        defaults.update(overrides)
        return Ple9_1Line(**defaults)

    def test_19_columns(self):
        cols = render_line(self._line()).split("|")
        self.assertEqual(len(cols), PLE_ACTIVOS_COLUMNS + 1)

    def test_period_is_annual(self):
        cols = render_line(self._line()).split("|")
        self.assertTrue(cols[0].endswith("1200"))

    def test_asset_name_strips_pipes(self):
        cols = render_line(self._line(asset_name="Dell | XPS | 15")).split("|")
        self.assertEqual(cols[5], "Dell   XPS   15")

    def test_amounts_2_decimals(self):
        cols = render_line(self._line(historical_value=Decimal("12500.5"))).split("|")
        # cols[14] = historical_value
        self.assertEqual(cols[14], "12500.50")


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle9_1Generator(TransactionCase):
    """Soft dependency: si account.asset no existe, iter_lines() devuelve vacío."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Activos",
                "country_id": cls.pe.id,
                "vat": "20131312955",
            }
        )

    def test_no_account_asset_model_returns_empty(self):
        """En Odoo CE sin OCA account_asset_management, devuelve 0 líneas."""
        gen = Ple9_1Generator(self.env, self.company, "202612")
        lines = list(gen.iter_lines())
        # Si el modelo no existe → vacío (no error)
        if self.env.get("account.asset") is None:
            self.assertEqual(lines, [])
        else:
            self.assertIsInstance(lines, list)

    def test_period_is_annual_yyyy1200(self):
        gen = Ple9_1Generator(self.env, self.company, "202612")
        self.assertEqual(gen.period, "20261200")
