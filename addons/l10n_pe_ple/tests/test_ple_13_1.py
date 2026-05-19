# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.ple_13_1_inv_valorizado import (
    OP_COMPRA,
    PLE_INV_VAL_COLUMNS,
    Ple13_1Generator,
    Ple13_1Line,
    render_line,
)


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle13_1Render(TransactionCase):
    def _line(self, **overrides):
        defaults = {
            "period": "20260400",
            "cuo": 1,
            "correlativo": "V00000001",
            "op_type": OP_COMPRA,
            "op_date": date(2026, 4, 15),
            "product_code": "PROD001",
            "product_name": "Producto X",
            "entry_qty": Decimal("10"),
            "entry_unit_cost": Decimal("5.0"),
            "entry_total_cost": Decimal("50.0"),
            "balance_qty": Decimal("10"),
            "balance_unit_cost": Decimal("5.0"),
            "balance_total_cost": Decimal("50.0"),
        }
        defaults.update(overrides)
        return Ple13_1Line(**defaults)

    def test_18_columns(self):
        cols = render_line(self._line()).split("|")
        self.assertEqual(len(cols), PLE_INV_VAL_COLUMNS + 1)

    def test_unit_cost_4_decimals(self):
        cols = render_line(self._line(entry_unit_cost=Decimal("12.5"))).split("|")
        self.assertEqual(cols[9], "12.5000")

    def test_total_cost_2_decimals(self):
        cols = render_line(self._line(entry_total_cost=Decimal("125.5"))).split("|")
        self.assertEqual(cols[10], "125.50")

    def test_period_anual_or_monthly(self):
        cols = render_line(self._line()).split("|")
        # Asumimos monthly (YYYYMM00)
        self.assertEqual(cols[0], "20260400")


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle13_1Generator(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Inv Val",
                "country_id": cls.pe.id,
                "vat": "20131312955",
            }
        )

    def test_returns_iterator_without_error(self):
        gen = Ple13_1Generator(self.env, self.company, "202604")
        lines = list(gen.iter_lines())
        self.assertIsInstance(lines, list)
