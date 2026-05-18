# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPleWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PLE Wizard Co",
                "country_id": cls.pe.id,
                "vat": "20131312955",
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "CLI W SAC",
                "country_id": cls.pe.id,
                "vat": "20100047218",
                "l10n_latam_identification_type_id": cls.env.ref("l10n_pe.it_RUC").id,
            }
        )
        # 1 venta abril 2026 (bypass validación l10n_latam via SQL)
        m = (
            cls.env["account.move"]
            .with_company(cls.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": cls.partner.id,
                    "company_id": cls.company.id,
                    "invoice_date": date(2026, 4, 10),
                    "date": date(2026, 4, 10),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "X",
                                "quantity": 1,
                                "price_unit": 100.0,
                                "tax_ids": [],
                            },
                        )
                    ],
                }
            )
        )
        cls.env.cr.execute("UPDATE account_move SET state='posted' WHERE id=%s", (m.id,))
        m.invalidate_recordset()

    def _make_wizard(self, period="202604", libro="14_1"):
        return self.env["l10n.pe.ple.wizard"].create(
            {
                "company_id": self.company.id,
                "period_yyyymm": period,
                "libro": libro,
            }
        )

    def test_generate_returns_file(self):
        wiz = self._make_wizard()
        wiz.action_generate()
        self.assertTrue(wiz.file_data)
        self.assertTrue(wiz.file_name.startswith("LE20131312955"))
        self.assertTrue(wiz.file_name.endswith(".txt"))
        self.assertGreaterEqual(wiz.line_count, 1)
        # El contenido decodificado tiene líneas separadas por CRLF
        content = base64.b64decode(wiz.file_data).decode("utf-8")
        self.assertIn("\r\n", content)

    def test_generate_ventas_filename(self):
        wiz = self._make_wizard(libro="14_1")
        wiz.action_generate()
        # Libro 140100 en posiciones 21-26 del filename
        self.assertIn("140100", wiz.file_name)

    def test_generate_compras_filename(self):
        wiz = self._make_wizard(libro="8_1")
        wiz.action_generate()
        self.assertIn("080100", wiz.file_name)

    def test_invalid_period_raises(self):
        wiz = self._make_wizard(period="2026")
        with self.assertRaisesRegex(UserError, "YYYYMM"):
            wiz.action_generate()

    def test_company_without_ruc_raises(self):
        co = self.env["res.company"].create(
            {
                "name": "NoRUC",
                "country_id": self.pe.id,
            }
        )
        wiz = self.env["l10n.pe.ple.wizard"].create(
            {
                "company_id": co.id,
                "period_yyyymm": "202604",
                "libro": "14_1",
            }
        )
        with self.assertRaisesRegex(UserError, "RUC"):
            wiz.action_generate()

    def test_empty_period_marks_no_movements_in_filename(self):
        wiz = self._make_wizard(period="202507")  # futuro, sin moves
        wiz.action_generate()
        # oper=0, info=0 → "00" en posiciones 27-28 (oper+info)
        # filename: LE + 11 + 8 + 6 + 4 (oper+info+mon+mix)
        # Pos 27-28 son oper+info
        self.assertEqual(wiz.line_count, 0)
        # En "LE20131312955202507001401000011.txt" → oper=0 info=0 currency=1 mix=1
        self.assertTrue(wiz.file_name.endswith("0011.txt"))
