# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import io
from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.ple_6_1_mayor import (
    PLE_MAYOR_COLUMNS,
    Ple6_1Generator,
    Ple6_1Line,
    render_line,
)


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle6_1Render(TransactionCase):
    """Render unitario sin ORM (8 columnas, formato SUNAT)."""

    def _line(self, **overrides):
        defaults = {
            "period": "20260400",
            "cuo": 1,
            "correlativo": "M00000001",
            "account_code": "6011",
            "account_name": "Mercaderías",
            "debit": Decimal("100.00"),
            "credit": Decimal("0.00"),
        }
        defaults.update(overrides)
        return Ple6_1Line(**defaults)

    def test_line_has_8_columns(self):
        cols = render_line(self._line()).split("|")
        # 8 columnas + el | final = 9 elementos al split
        self.assertEqual(len(cols), PLE_MAYOR_COLUMNS + 1)

    def test_line_ends_with_pipe(self):
        self.assertTrue(render_line(self._line()).endswith("|"))

    def test_period_first_col(self):
        cols = render_line(self._line()).split("|")
        self.assertEqual(cols[0], "20260400")

    def test_account_code_in_col_3(self):
        cols = render_line(self._line()).split("|")
        # cols[3] = account_code (0-indexed)
        self.assertEqual(cols[3], "6011")

    def test_debit_credit_two_decimals(self):
        cols = render_line(self._line(debit=Decimal("250.5"), credit=Decimal("0"))).split("|")
        # cols[5] = debit, cols[6] = credit
        self.assertEqual(cols[5], "250.50")
        self.assertEqual(cols[6], "0.00")

    def test_account_name_strips_pipes(self):
        cols = render_line(self._line(account_name="Caja | y | bancos")).split("|")
        # cols[4] = account_name (post-clean)
        self.assertEqual(cols[4], "Caja   y   bancos")

    def test_state_in_last_col(self):
        cols = render_line(self._line()).split("|")
        # cols[7] = state
        self.assertEqual(cols[7], "1")


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle6_1Generator(TransactionCase):
    """E2E: account.move.line posteados → agregado por cuenta → TXT Mayor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        # Company nueva para aislarse de tests previos con AML reconciliados
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Mayor",
                "country_id": cls.pe.id,
                "vat": "20131312955",
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.env = cls.env(user=cls.env.user.with_company(cls.company))
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Mayor",
                "country_id": cls.pe.id,
            }
        )

    def _create_posted_move(self, day: int, amount: float):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 4, day),
                "date": date(2026, 4, day),
                "name": f"F-MAY-{day:08d}",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "X",
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [],
                        },
                    )
                ],
            }
        )
        self.env.cr.execute("UPDATE account_move SET state='posted' WHERE id=%s", (move.id,))
        move.invalidate_recordset()
        self.env.cr.execute(
            "UPDATE account_move_line SET parent_state='posted' WHERE move_id=%s",
            (move.id,),
        )
        return move

    def test_aggregates_by_account(self):
        # Dos facturas mismo período → mismas cuentas, sumas combinadas
        self._create_posted_move(10, 100.0)
        self._create_posted_move(15, 50.0)
        gen = Ple6_1Generator(self.env, self.company, "202604")
        lines = list(gen.iter_lines())
        # Al menos 2 cuentas (cliente + ingreso); no por línea de aml
        self.assertGreaterEqual(len(lines), 2)
        # Y debe ser menor que el número total de aml (4: 2 por factura)
        # — porque agrupa por cuenta
        self.assertLessEqual(len(lines), 4)

    def test_skips_other_periods(self):
        self._create_posted_move(10, 100.0)
        m_mayo = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 5, 1),
                "date": date(2026, 5, 1),
                "name": "F-MAY-MAYO",
                "invoice_line_ids": [
                    (0, 0, {"name": "Mayo", "quantity": 1, "price_unit": 999.0, "tax_ids": []})
                ],
            }
        )
        self.env.cr.execute("UPDATE account_move SET state='posted' WHERE id=%s", (m_mayo.id,))
        self.env.cr.execute(
            "UPDATE account_move_line SET parent_state='posted' WHERE move_id=%s",
            (m_mayo.id,),
        )
        m_mayo.invalidate_recordset()
        lines = list(Ple6_1Generator(self.env, self.company, "202604").iter_lines())
        # El monto 999.0 de mayo no debe aparecer en abril
        joined = "\n".join(lines)
        self.assertNotIn("999.00", joined)

    def test_generate_to_file_crlf(self):
        self._create_posted_move(10, 100.0)
        buf = io.BytesIO()
        count = Ple6_1Generator(self.env, self.company, "202604").generate_to_file(buf)
        self.assertGreaterEqual(count, 1)
        content = buf.getvalue().decode("utf-8")
        self.assertIn("\r\n", content)
        for ln in [x for x in content.split("\r\n") if x]:
            self.assertTrue(ln.endswith("|"))
            # 8 columnas (split por | da 9 trozos: 8 valores + 1 vacío al final)
            self.assertEqual(len(ln.split("|")), PLE_MAYOR_COLUMNS + 1)

    def test_skips_accounts_without_movements(self):
        """Cuentas con SUM(debit)=SUM(credit)=0 NO deben aparecer en el TXT."""
        self._create_posted_move(10, 100.0)
        lines = list(Ple6_1Generator(self.env, self.company, "202604").iter_lines())
        for ln in lines:
            cols = ln.split("|")
            debit = Decimal(cols[5])
            credit = Decimal(cols[6])
            self.assertTrue(
                debit != 0 or credit != 0,
                f"Cuenta sin movimiento no debe estar: {ln}",
            )
