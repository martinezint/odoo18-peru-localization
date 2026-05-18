# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.ple_8_1_compras import (
    PLE_COMPRAS_COLUMNS,
    Ple8_1Generator,
    Ple8_1Line,
    render_line,
)


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle8_1Render(TransactionCase):

    def _minimal_line(self):
        return Ple8_1Line(
            period="20260400",
            cuo=1,
            correlativo="MF001-1",
            issue_date=date(2026, 4, 15),
            doc_type="01",
            serie="F001",
            initial_number="1",
            final_number="1",
            supplier_id_type="6",
            supplier_id="20100047218",
            supplier_name="PROVEEDOR TEST SAC",
            taxed_base_no_export=Decimal("100.00"),
            igv_no_export=Decimal("18.00"),
            total=Decimal("118.00"),
            currency="PEN",
        )

    def test_line_has_52_columns(self):
        line = self._minimal_line()
        out = render_line(line)
        cols = out.split("|")
        self.assertEqual(len(cols), PLE_COMPRAS_COLUMNS + 1)

    def test_line_ends_with_pipe(self):
        line = self._minimal_line()
        self.assertTrue(render_line(line).endswith("|"))

    def test_line_supplier_id_at_col_12(self):
        line = self._minimal_line()
        cols = render_line(line).split("|")
        self.assertEqual(cols[11], "20100047218")

    def test_line_igv_no_export(self):
        line = self._minimal_line()
        cols = render_line(line).split("|")
        # cols[18] = igv_no_export (col 19, 0-indexed 18)
        self.assertEqual(cols[18], "18.00")


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle8_1Generator(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create({
            "name": "Test PLE Compras Co",
            "country_id": cls.pe.id,
            "vat": "20131312955",
        })
        cls.env["account.chart.template"].try_loading(
            "pe", company=cls.company, install_demo=False
        )
        cls.supplier = cls.env["res.partner"].create({
            "name": "PROVEEDOR PLE SAC",
            "country_id": cls.pe.id,
            "vat": "20100047218",
            "l10n_latam_identification_type_id": cls.env.ref("l10n_pe.it_RUC").id,
        })

    def _create_bill(self, day: int, amount: float):
        bill = self.env["account.move"].with_company(self.company).create({
            "move_type": "in_invoice",
            "partner_id": self.supplier.id,
            "company_id": self.company.id,
            "invoice_date": date(2026, 4, day),
            "date": date(2026, 4, day),
            "ref": f"F001-{day}",
            "invoice_line_ids": [(0, 0, {
                "name": "Compra test", "quantity": 1, "price_unit": amount,
                "tax_ids": [],
            })],
        })
        # Bypass validación l10n_latam — fuera del scope del test.
        self.env.cr.execute(
            "UPDATE account_move SET state='posted' WHERE id=%s", (bill.id,)
        )
        bill.invalidate_recordset()
        return bill

    def test_generator_picks_in_invoices(self):
        b1 = self._create_bill(10, 100.0)
        b2 = self._create_bill(15, 200.0)
        gen = Ple8_1Generator(self.env, self.company, "202604")
        lines = list(gen.iter_lines())
        joined = "\n".join(lines)
        self.assertIn(f"M{b1.id:08d}", joined)
        self.assertIn(f"M{b2.id:08d}", joined)

    def test_out_invoice_not_in_compras(self):
        sale = self.env["account.move"].with_company(self.company).create({
            "move_type": "out_invoice",
            "partner_id": self.supplier.id,
            "company_id": self.company.id,
            "invoice_date": date(2026, 4, 10),
            "date": date(2026, 4, 10),
            "invoice_line_ids": [(0, 0, {
                "name": "Venta", "quantity": 1, "price_unit": 100.0,
                "tax_ids": [],
            })],
        })
        self.env.cr.execute(
            "UPDATE account_move SET state='posted' WHERE id=%s", (sale.id,)
        )
        sale.invalidate_recordset()
        lines = list(Ple8_1Generator(self.env, self.company, "202604").iter_lines())
        self.assertNotIn(f"M{sale.id:08d}", "\n".join(lines))
