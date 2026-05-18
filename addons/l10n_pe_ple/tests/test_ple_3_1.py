# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.ple_3_1_inventario import (
    BALANCE_CLASSES,
    PLE_INVENTARIO_COLUMNS,
    Ple3_1Generator,
    Ple3_1Line,
    render_line,
)


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle3_1Render(TransactionCase):
    """Render unitario sin ORM."""

    def _line(self, **overrides):
        defaults = {
            "period": "20260000",
            "cuo": 1,
            "correlativo": "B00000001",
            "account_code": "1011",
            "account_name": "Caja",
            "debit_balance": Decimal("5000.00"),
            "credit_balance": Decimal("0.00"),
        }
        defaults.update(overrides)
        return Ple3_1Line(**defaults)

    def test_8_columns(self):
        cols = render_line(self._line()).split("|")
        self.assertEqual(len(cols), PLE_INVENTARIO_COLUMNS + 1)

    def test_period_anual_yyyy0000(self):
        cols = render_line(self._line()).split("|")
        self.assertEqual(cols[0], "20260000")
        self.assertTrue(cols[0].endswith("0000"))

    def test_balance_classes_constant(self):
        self.assertEqual(BALANCE_CLASSES, ("1", "2", "3", "4", "5"))


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle3_1Generator(TransactionCase):
    """E2E: AML posteados → solo cuentas balance (clase 1-5)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Inventario",
                "country_id": cls.pe.id,
                "vat": "20131312955",
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.env = cls.env(user=cls.env.user.with_company(cls.company))
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Bal", "country_id": cls.pe.id}
        )

    def _post_move(self, day: int, amount: float):
        m = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 4, day),
                "date": date(2026, 4, day),
                "name": f"F-BAL-{day:08d}",
                "invoice_line_ids": [
                    (0, 0, {"name": "X", "quantity": 1, "price_unit": amount, "tax_ids": []})
                ],
            }
        )
        self.env.cr.execute("UPDATE account_move SET state='posted' WHERE id=%s", (m.id,))
        self.env.cr.execute(
            "UPDATE account_move_line SET parent_state='posted' WHERE move_id=%s", (m.id,)
        )
        m.invalidate_recordset()
        return m

    def test_outputs_only_balance_classes(self):
        """Las líneas emitidas deben tener código que empieza por 1-5."""
        self._post_move(10, 1000.0)
        lines = list(Ple3_1Generator(self.env, self.company, "202604").iter_lines())
        for ln in lines:
            cols = ln.split("|")
            code = cols[3]
            if not code:
                continue
            self.assertIn(
                code[0],
                BALANCE_CLASSES,
                f"Cuenta {code} no es de balance (clase 6-7-8-9)",
            )

    def test_period_in_output_is_annual(self):
        self._post_move(10, 1000.0)
        lines = list(Ple3_1Generator(self.env, self.company, "202604").iter_lines())
        for ln in lines:
            cols = ln.split("|")
            self.assertEqual(cols[0], "20260000")  # period anual

    def test_at_least_one_line_emitted(self):
        self._post_move(10, 1000.0)
        lines = list(Ple3_1Generator(self.env, self.company, "202604").iter_lines())
        # Una venta sin IGV genera al menos: cliente (clase 1) + ingreso (clase 7)
        # → solo la cuenta cliente (clase 1) entra en el output.
        self.assertGreaterEqual(len(lines), 1)
