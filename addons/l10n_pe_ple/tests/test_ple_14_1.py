# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import io
from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.ple_14_1_ventas import (
    PLE_VENTAS_COLUMNS,
    Ple14_1Generator,
    Ple14_1Line,
    render_line,
)


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle14_1Render(TransactionCase):
    """Tests del render de líneas individuales (sin Odoo ORM)."""

    def _minimal_line(self):
        return Ple14_1Line(
            period="20260400",
            cuo=1,
            correlativo="MF001-1",
            issue_date=date(2026, 4, 15),
            doc_type="01",
            serie="F001",
            number="1",
            customer_id_type="6",
            customer_id="20100047218",
            customer_name="CLIENTE TEST SAC",
            taxed_base=Decimal("100.00"),
            igv=Decimal("18.00"),
            total=Decimal("118.00"),
            currency="PEN",
        )

    def test_line_has_46_columns(self):
        line = self._minimal_line()
        out = render_line(line)
        cols = out.split("|")
        # split por '|' devuelve N+1 partes si la línea termina con '|'
        self.assertEqual(len(cols), PLE_VENTAS_COLUMNS + 1)
        self.assertEqual(cols[-1], "")  # último vacío post-pipe

    def test_line_ends_with_pipe(self):
        line = self._minimal_line()
        self.assertTrue(render_line(line).endswith("|"))

    def test_line_period_first(self):
        line = self._minimal_line()
        cols = render_line(line).split("|")
        self.assertEqual(cols[0], "20260400")

    def test_line_amounts_two_decimals(self):
        line = self._minimal_line()
        cols = render_line(line).split("|")
        # cols[13] = taxed_base, cols[15] = igv, cols[21] = total
        self.assertEqual(cols[13], "100.00")
        self.assertEqual(cols[15], "18.00")
        self.assertEqual(cols[21], "118.00")

    def test_line_date_dd_mm_yyyy(self):
        line = self._minimal_line()
        cols = render_line(line).split("|")
        # cols[3] = issue_date
        self.assertEqual(cols[3], "15/04/2026")

    def test_pipe_in_name_is_stripped(self):
        line = self._minimal_line()
        line.customer_name = "EMPRESA | CON | PIPES"
        out = render_line(line).split("|")
        # cols[11] = customer_name; los pipes internos se reemplazan por espacios
        self.assertEqual(out[11], "EMPRESA   CON   PIPES")

    def test_empty_date_renders_empty(self):
        line = self._minimal_line()
        line.due_date = None
        cols = render_line(line).split("|")
        # cols[4] = due_date
        self.assertEqual(cols[4], "")

    def test_exchange_rate_three_decimals(self):
        line = self._minimal_line()
        line.exchange_rate = Decimal("3.752")
        cols = render_line(line).split("|")
        # cols[23] = exchange_rate
        self.assertEqual(cols[23], "3.752")


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle14_1Generator(TransactionCase):
    """E2E: account.move → PLE TXT."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create({
            "name": "Test PLE Co",
            "country_id": cls.pe.id,
            "vat": "20131312955",
        })
        cls.env["account.chart.template"].try_loading(
            "pe", company=cls.company, install_demo=False
        )
        cls.partner = cls.env["res.partner"].create({
            "name": "CLIENTE PLE SAC",
            "country_id": cls.pe.id,
            "vat": "20100047218",
            "l10n_latam_identification_type_id": cls.env.ref("l10n_pe.it_RUC").id,
        })

    def _create_posted_move(self, day: int, amount: float, move_type="out_invoice"):
        """Crea + fuerza state=posted vía SQL para bypasear validación l10n_latam
        (número de documento), que NO es responsabilidad del módulo PLE."""
        move = self.env["account.move"].with_company(self.company).create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "invoice_date": date(2026, 4, day),
            "date": date(2026, 4, day),
            "invoice_line_ids": [(0, 0, {
                "name": "Test",
                "quantity": 1,
                "price_unit": amount,
                "tax_ids": [],
            })],
        })
        self.env.cr.execute(
            "UPDATE account_move SET state='posted' WHERE id=%s", (move.id,)
        )
        move.invalidate_recordset()
        return move

    def test_generator_produces_one_line_per_move(self):
        m1 = self._create_posted_move(10, 100.0)
        m2 = self._create_posted_move(15, 200.0)
        gen = Ple14_1Generator(self.env, self.company, "202604")
        lines = list(gen.iter_lines())
        # solo nuestras 2 moves (otras BD pueden tener otras del setUp de otros tests)
        # → filtramos por correlativo M<id>
        our = [l for l in lines if f"M{m1.id:08d}" in l or f"M{m2.id:08d}" in l]
        self.assertEqual(len(our), 2)

    def test_generator_skips_other_periods(self):
        self._create_posted_move(10, 100.0)
        # Move en mayo, no debe aparecer en período 202604
        m_mayo = self.env["account.move"].with_company(self.company).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "invoice_date": date(2026, 5, 1),
            "date": date(2026, 5, 1),
            "invoice_line_ids": [(0, 0, {
                "name": "Mayo", "quantity": 1, "price_unit": 50.0,
                "tax_ids": [],
            })],
        })
        self.env.cr.execute(
            "UPDATE account_move SET state='posted' WHERE id=%s", (m_mayo.id,)
        )
        m_mayo.invalidate_recordset()
        lines = list(Ple14_1Generator(self.env, self.company, "202604").iter_lines())
        self.assertNotIn(f"M{m_mayo.id:08d}", "\n".join(lines))

    def test_generate_to_file_writes_crlf_lines(self):
        self._create_posted_move(10, 100.0)
        self._create_posted_move(15, 200.0)
        buf = io.BytesIO()
        count = Ple14_1Generator(self.env, self.company, "202604").generate_to_file(buf)
        self.assertGreaterEqual(count, 2)
        content = buf.getvalue().decode("utf-8")
        # SUNAT acepta CRLF
        self.assertIn("\r\n", content)
        # Cada línea termina con '|'
        non_empty = [l for l in content.split("\r\n") if l]
        for line in non_empty:
            self.assertTrue(line.endswith("|"), f"línea no termina con |: {line[:80]}")

    def test_in_invoice_not_included(self):
        """Compras no deben aparecer en el registro de Ventas."""
        bill = self.env["account.move"].with_company(self.company).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "invoice_date": date(2026, 4, 10),
            "date": date(2026, 4, 10),
            "invoice_line_ids": [(0, 0, {
                "name": "Compra", "quantity": 1, "price_unit": 100.0,
                "tax_ids": [],
            })],
        })
        self.env.cr.execute(
            "UPDATE account_move SET state='posted' WHERE id=%s", (bill.id,)
        )
        bill.invalidate_recordset()
        lines = list(Ple14_1Generator(self.env, self.company, "202604").iter_lines())
        self.assertNotIn(f"M{bill.id:08d}", "\n".join(lines))
