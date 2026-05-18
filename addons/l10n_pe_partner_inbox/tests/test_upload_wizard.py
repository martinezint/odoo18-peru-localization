# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .test_ubl_parser import SAMPLE_CREDIT_NOTE_XML, SAMPLE_INVOICE_XML


@tagged("post_install", "-at_install", "l10n_pe_partner_inbox")
class TestUploadWizard(TransactionCase):
    """End-to-end: upload XML → wizard crea draft account.move."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["l10n.pe.upload.supplier.xml"]

    def _make_wizard(self, xml_bytes, filename="test.xml", auto_create=True):
        return self.Wizard.create(
            {
                "xml_file": base64.b64encode(xml_bytes),
                "xml_filename": filename,
                "auto_create_partner": auto_create,
            }
        )

    def test_creates_draft_bill_from_invoice(self):
        wizard = self._make_wizard(SAMPLE_INVOICE_XML)
        action = wizard.action_parse_and_create()
        self.assertEqual(action["res_model"], "account.move")
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(move.move_type, "in_invoice")
        self.assertEqual(move.ref, "F001-00000123")
        self.assertEqual(move.partner_id.vat, "20131312955")
        self.assertEqual(len(move.invoice_line_ids), 1)
        self.assertEqual(move.invoice_line_ids[0].name, "Servicio de consultoría")
        self.assertEqual(move.invoice_line_ids[0].quantity, 2.0)
        self.assertEqual(move.invoice_line_ids[0].price_unit, 100.0)

    def test_credit_note_creates_in_refund(self):
        wizard = self._make_wizard(SAMPLE_CREDIT_NOTE_XML)
        action = wizard.action_parse_and_create()
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(move.move_type, "in_refund")

    def test_partner_auto_created_when_unknown_ruc(self):
        # Verifica que no exista partner con ese RUC antes
        ruc = "20131312955"
        existing = self.env["res.partner"].search([("vat", "=", ruc)])
        existing.unlink()
        wizard = self._make_wizard(SAMPLE_INVOICE_XML, auto_create=True)
        wizard.action_parse_and_create()
        partner = self.env["res.partner"].search([("vat", "=", ruc)], limit=1)
        self.assertTrue(partner)
        self.assertEqual(partner.name, "SUPERINTENDENCIA NACIONAL DE ADUANAS")
        self.assertTrue(partner.is_company)

    def test_partner_reused_when_ruc_exists(self):
        ruc = "20131312955"
        existing = self.env["res.partner"].search([("vat", "=", ruc)])
        existing.unlink()
        # Crea partner manualmente
        partner = self.env["res.partner"].create(
            {
                "name": "Existing Partner Name",
                "vat": ruc,
                "country_id": self.env.ref("base.pe").id,
                "l10n_latam_identification_type_id": self.env.ref("l10n_pe.it_RUC").id,
            }
        )
        wizard = self._make_wizard(SAMPLE_INVOICE_XML)
        action = wizard.action_parse_and_create()
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(
            move.partner_id, partner, "Debe reusar el partner existente, no crear duplicado"
        )

    def test_raises_when_auto_create_off_and_partner_unknown(self):
        ruc = "20131312955"
        self.env["res.partner"].search([("vat", "=", ruc)]).unlink()
        wizard = self._make_wizard(SAMPLE_INVOICE_XML, auto_create=False)
        with self.assertRaisesRegex(UserError, "no está registrado"):
            wizard.action_parse_and_create()

    # Nota: test de "xml_file vacío" eliminado porque el field es required=True,
    # Odoo bloquea la creación del wizard con xml_file=False antes de llegar
    # a la validación interna.

    def test_xml_attached_to_move(self):
        wizard = self._make_wizard(SAMPLE_INVOICE_XML, filename="invoice.xml")
        action = wizard.action_parse_and_create()
        move = self.env["account.move"].browse(action["res_id"])
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
            ]
        )
        self.assertTrue(attachments, "Debe haber adjunto un XML al move")
        xml_attach = attachments.filtered(lambda a: a.mimetype == "application/xml")
        self.assertTrue(xml_attach)
        self.assertEqual(xml_attach.name, "invoice.xml")
