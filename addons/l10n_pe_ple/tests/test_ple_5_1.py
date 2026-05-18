# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import io
from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.ple_5_1_diario import (
    PLE_DIARIO_COLUMNS,
    Ple5_1Generator,
    Ple5_1Line,
    render_line,
)


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle5_1Render(TransactionCase):
    """Tests del render de líneas individuales (sin Odoo ORM)."""

    def _minimal_line(self):
        return Ple5_1Line(
            period="20260400",
            cuo=1,
            correlativo="M00000001",
            account_code="6011",
            currency="PEN",
            doc_type="01",
            serie="F001",
            number="123",
            accounting_date=date(2026, 4, 15),
            glosa="Compra mercaderías",
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        )

    def test_line_has_32_columns(self):
        line = self._minimal_line()
        out = render_line(line)
        cols = out.split("|")
        self.assertEqual(len(cols), PLE_DIARIO_COLUMNS + 1)

    def test_line_ends_with_pipe(self):
        line = self._minimal_line()
        self.assertTrue(render_line(line).endswith("|"))

    def test_period_in_first_col(self):
        cols = render_line(self._minimal_line()).split("|")
        self.assertEqual(cols[0], "20260400")

    def test_account_code_in_col_3(self):
        cols = render_line(self._minimal_line()).split("|")
        # cols[3] = account_code
        self.assertEqual(cols[3], "6011")

    def test_debit_credit_two_decimals(self):
        line = self._minimal_line()
        line.debit = Decimal("100.5")
        line.credit = Decimal("0")
        cols = render_line(line).split("|")
        # cols[17] = debit, cols[18] = credit
        self.assertEqual(cols[17], "100.50")
        self.assertEqual(cols[18], "0.00")

    def test_glosa_strips_pipes(self):
        line = self._minimal_line()
        line.glosa = "Texto | con | pipes"
        cols = render_line(line).split("|")
        # cols[15] = glosa (post-clean)
        self.assertEqual(cols[15], "Texto   con   pipes")

    def test_date_format_dd_mm_yyyy(self):
        cols = render_line(self._minimal_line()).split("|")
        self.assertEqual(cols[13], "15/04/2026")


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle5_1Generator(TransactionCase):
    """E2E: account.move.line posteados → líneas TXT PLE 5.1."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        # Empresa NUEVA: evita conflictos con asientos reconciliados de
        # tests previos en la suite (try_loading falla si el chart se intenta
        # aplicar sobre una company con AML reconciliados).
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Diario",
                "country_id": cls.pe.id,
                "vat": "20131312955",
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        # Operamos en contexto multi-company de la empresa nueva.
        cls.env = cls.env(user=cls.env.user.with_company(cls.company))
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Diario",
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
                "name": f"F-DIA-{day:08d}",
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
        # parent_state es store=True related; reseteamos las líneas para
        # forzar el recompute
        move.invalidate_recordset()
        self.env.cr.execute(
            "UPDATE account_move_line SET parent_state='posted' WHERE move_id=%s",
            (move.id,),
        )
        return move

    def test_generator_emits_one_line_per_aml(self):
        m = self._create_posted_move(10, 100.0)
        gen = Ple5_1Generator(self.env, self.company, "202604")
        lines = list(gen.iter_lines())
        # Filtramos solo las líneas de nuestro move (otras pueden estar en BD)
        ours = [ln for ln in lines if f"M{m.id:08d}" in ln]
        # account.move tipo out_invoice tiene N líneas de aml posteadas
        # (counterparty + base income; depende del setup). Como mínimo, 2.
        self.assertGreaterEqual(len(ours), 2)

    def test_generator_skips_other_periods(self):
        m = self._create_posted_move(10, 100.0)
        m_mayo = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 5, 1),
                "date": date(2026, 5, 1),
                "name": "F-MAY-001",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Mayo",
                            "quantity": 1,
                            "price_unit": 50.0,
                            "tax_ids": [],
                        },
                    )
                ],
            }
        )
        self.env.cr.execute("UPDATE account_move SET state='posted' WHERE id=%s", (m_mayo.id,))
        self.env.cr.execute(
            "UPDATE account_move_line SET parent_state='posted' WHERE move_id=%s",
            (m_mayo.id,),
        )
        m_mayo.invalidate_recordset()
        lines = list(Ple5_1Generator(self.env, self.company, "202604").iter_lines())
        joined = "\n".join(lines)
        self.assertNotIn(f"M{m_mayo.id:08d}", joined)
        # pero el de abril sí
        self.assertIn(f"M{m.id:08d}", joined)

    def test_generate_to_file_crlf(self):
        self._create_posted_move(10, 100.0)
        buf = io.BytesIO()
        count = Ple5_1Generator(self.env, self.company, "202604").generate_to_file(buf)
        self.assertGreaterEqual(count, 1)
        content = buf.getvalue().decode("utf-8")
        self.assertIn("\r\n", content)
        non_empty = [ln for ln in content.split("\r\n") if ln]
        for ln in non_empty:
            self.assertTrue(ln.endswith("|"), f"línea no termina con |: {ln[:80]}")
