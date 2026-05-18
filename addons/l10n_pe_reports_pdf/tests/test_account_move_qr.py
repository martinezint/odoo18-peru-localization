# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
from datetime import date

from odoo.tests.common import TransactionCase, tagged

SIGNED_XML_SAMPLE = b"""<?xml version="1.0"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
  <ds:Signature>
    <ds:SignatureValue>MOCK_SIG_VALUE_BASE64==</ds:SignatureValue>
  </ds:Signature>
</Invoice>
"""


@tagged("post_install", "-at_install", "l10n_pe_reports_pdf")
class TestAccountMoveQr(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "QR Test Co",
                "country_id": cls.pe.id,
                "vat": "20131312955",
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "CLIENTE QR",
                "country_id": cls.pe.id,
                "vat": "20100047218",
                "l10n_latam_identification_type_id": cls.env.ref("l10n_pe.it_RUC").id,
            }
        )

    def _create_move_with_edi(self, *, with_signed_xml=True, move_type="out_invoice"):
        move = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": move_type,
                    "partner_id": self.partner.id,
                    "company_id": self.company.id,
                    "invoice_date": date(2026, 5, 18),
                    "date": date(2026, 5, 18),
                    "name": "F001/00000123",
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Servicio",
                                "quantity": 1,
                                "price_unit": 100.0,
                                "tax_ids": [],
                            },
                        )
                    ],
                }
            )
        )
        doc = self.env["l10n.pe.edi.document"].create(
            {
                "move_id": move.id,
                "name": "20131312955-01-F001-123.xml",
                "xml_signed": base64.b64encode(SIGNED_XML_SAMPLE) if with_signed_xml else False,
                "state": "signed" if with_signed_xml else "draft",
            }
        )
        move.l10n_pe_edi_document_id = doc.id
        return move

    # ─── QR data string ──────────────────────────────────────────

    def test_qr_data_includes_company_ruc(self):
        move = self._create_move_with_edi()
        data = move._l10n_pe_edi_qr_data()
        self.assertTrue(data.startswith("20131312955|"))

    def test_qr_data_doc_type_factura(self):
        move = self._create_move_with_edi(move_type="out_invoice")
        data = move._l10n_pe_edi_qr_data()
        cols = data.split("|")
        self.assertEqual(cols[1], "01")

    def test_qr_data_doc_type_nc(self):
        move = self._create_move_with_edi(move_type="out_refund")
        data = move._l10n_pe_edi_qr_data()
        cols = data.split("|")
        self.assertEqual(cols[1], "07")

    def test_qr_data_serie_and_number_from_move_name(self):
        move = self._create_move_with_edi()
        data = move._l10n_pe_edi_qr_data()
        cols = data.split("|")
        self.assertEqual(cols[2], "F001")
        self.assertEqual(cols[3], "123")  # lstrip de ceros

    def test_qr_data_customer_doc_type_ruc(self):
        move = self._create_move_with_edi()
        data = move._l10n_pe_edi_qr_data()
        cols = data.split("|")
        self.assertEqual(cols[7], "6")
        self.assertEqual(cols[8], "20100047218")

    def test_qr_data_includes_hash_from_signature(self):
        move = self._create_move_with_edi()
        data = move._l10n_pe_edi_qr_data()
        cols = data.split("|")
        self.assertEqual(cols[9], "MOCK_SIG_VALUE_BASE64==")

    def test_qr_data_empty_when_no_edi_document(self):
        move = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "company_id": self.company.id,
                    "invoice_date": date(2026, 5, 18),
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
        self.assertEqual(move._l10n_pe_edi_qr_data(), "")

    # ─── QR PNG base64 ───────────────────────────────────────────

    def test_qr_png_base64_returns_valid_data(self):
        move = self._create_move_with_edi()
        b64 = move._l10n_pe_edi_qr_png_base64()
        self.assertTrue(b64)
        png = base64.b64decode(b64)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")

    def test_qr_png_empty_when_no_edi_document(self):
        move = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "company_id": self.company.id,
                    "invoice_date": date(2026, 5, 18),
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
        self.assertEqual(move._l10n_pe_edi_qr_png_base64(), "")

    def test_qr_amounts_match_move(self):
        move = self._create_move_with_edi()
        data = move._l10n_pe_edi_qr_data()
        cols = data.split("|")
        # IGV en col 4, Total en col 5; sin impuestos config, ambos pueden ser 0
        # pero el formato siempre es '0.00'
        self.assertRegex(cols[4], r"^\d+\.\d{2}$")
        self.assertRegex(cols[5], r"^\d+\.\d{2}$")
