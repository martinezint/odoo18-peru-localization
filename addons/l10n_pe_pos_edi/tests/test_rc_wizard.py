# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_pos_edi")
class TestRcWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create({
            "name": "Test RC Co",
            "country_id": cls.pe.id,
            "vat": "20131312955",
        })
        cls.env["account.chart.template"].try_loading(
            "pe", company=cls.company, install_demo=False
        )
        cls.partner = cls.env["res.partner"].create({
            "name": "CLI RC",
            "country_id": cls.pe.id,
        })

    _boleta_seq = 0  # contador clase para nombres únicos

    @classmethod
    def _next_seq(cls):
        cls._boleta_seq += 1
        return cls._boleta_seq

    def _create_posted_boleta(self, day: int, total: float, serie: str = "B001"):
        """Crea + SQL-bypass-postea un move out_invoice (boleta para RC).

        Cada llamada usa un número distinto (counter clase) para evitar
        violar el unique constraint account_move_unique_name.
        """
        num = self._next_seq()
        m = self.env["account.move"].with_company(self.company).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "invoice_date": date(2026, 5, day),
            "date": date(2026, 5, day),
            "name": f"{serie}/{num:08d}",
            "invoice_line_ids": [(0, 0, {
                "name": "Producto", "quantity": 1, "price_unit": total,
                "tax_ids": [],
            })],
        })
        self.env.cr.execute(
            "UPDATE account_move SET state='posted' WHERE id=%s", (m.id,)
        )
        m.invalidate_recordset()
        return m

    def _make_wizard(self, ref_date=date(2026, 5, 17), correlativo=1, sign=False):
        return self.env["l10n.pe.rc.wizard"].create({
            "company_id": self.company.id,
            "reference_date": ref_date,
            "issue_date": date(2026, 5, 18),
            "correlativo": correlativo,
            "sign_xml": sign,
        })

    # ─── Casos sin boletas ───────────────────────────────────────

    def test_no_boletas_raises(self):
        wiz = self._make_wizard(ref_date=date(2027, 1, 1))  # día sin moves
        with self.assertRaisesRegex(UserError, "No hay boletas"):
            wiz.action_generate()

    def test_no_ruc_raises(self):
        no_ruc_co = self.env["res.company"].create({
            "name": "NoRUC Co",
            "country_id": self.pe.id,
        })
        wiz = self.env["l10n.pe.rc.wizard"].create({
            "company_id": no_ruc_co.id,
            "reference_date": date(2026, 5, 17),
            "issue_date": date(2026, 5, 18),
            "correlativo": 1,
            "sign_xml": False,
        })
        with self.assertRaisesRegex(UserError, "RUC"):
            wiz.action_generate()

    # ─── Casos con boletas ───────────────────────────────────────

    def test_generates_xml_with_one_boleta(self):
        self._create_posted_boleta(17, 118.0)
        wiz = self._make_wizard()
        wiz.action_generate()
        self.assertEqual(wiz.boletas_count, 1)
        self.assertTrue(wiz.xml_data)
        # filename SUNAT RC
        self.assertIn("RC-20260518-001", wiz.xml_filename)
        # XML válido (parseable)
        from lxml import etree
        xml = base64.b64decode(wiz.xml_data)
        root = etree.fromstring(xml)
        self.assertEqual(etree.QName(root.tag).localname, "SummaryDocuments")

    def test_generates_xml_with_multiple_boletas(self):
        for day_offset in range(3):
            self._create_posted_boleta(17, 100.0 + day_offset)
        wiz = self._make_wizard()
        wiz.action_generate()
        self.assertEqual(wiz.boletas_count, 3)

    def test_filename_includes_correlativo(self):
        self._create_posted_boleta(17, 118.0)
        wiz = self._make_wizard(correlativo=5)
        wiz.action_generate()
        self.assertIn("RC-20260518-005", wiz.xml_filename)

    def test_edi_document_created(self):
        self._create_posted_boleta(17, 118.0)
        wiz = self._make_wizard()
        wiz.action_generate()
        self.assertTrue(wiz.edi_document_id)
        self.assertEqual(wiz.edi_document_id.state, "draft")  # sign_xml=False
        self.assertTrue(wiz.edi_document_id.xml_unsigned)

    def test_skips_boletas_of_other_dates(self):
        self._create_posted_boleta(17, 100.0)  # día objetivo
        self._create_posted_boleta(18, 200.0)  # día siguiente, debe ser excluida
        wiz = self._make_wizard(ref_date=date(2026, 5, 17))
        wiz.action_generate()
        self.assertEqual(wiz.boletas_count, 1)
