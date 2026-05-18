# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import io
import zipfile

from odoo.tests.common import TransactionCase, tagged

from .test_ubl_parser import SAMPLE_INVOICE_XML


@tagged("post_install", "-at_install", "l10n_pe_partner_inbox")
class TestMailAliasInbox(TransactionCase):
    """Verifica que llegar emails con XMLs adjuntos cree borradores account.move.

    No usamos un mailgateway real: invocamos message_new directamente, como
    haría el gateway tras parsear el email, y luego comprobamos los efectos.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Inbox = cls.env["l10n.pe.partner.inbox.message"]

    def _create_msg_with_attachments(self, payloads):
        """payloads: lista de (filename, bytes). Crea la message + adjunta."""
        msg = self.Inbox.create(
            {
                "name": "Factura recibida",
                "email_from": "proveedor@example.com",
                "subject": "Factura F001-123",
            }
        )
        for name, raw in payloads:
            self.env["ir.attachment"].create(
                {
                    "name": name,
                    "datas": base64.b64encode(raw),
                    "res_model": msg._name,
                    "res_id": msg.id,
                    "mimetype": "application/xml" if name.endswith(".xml") else "application/zip",
                }
            )
        return msg

    def test_processes_xml_attachment(self):
        msg = self._create_msg_with_attachments([("factura.xml", SAMPLE_INVOICE_XML)])
        msg._process_email_attachments()
        self.assertEqual(msg.state, "processed")
        self.assertEqual(len(msg.created_move_ids), 1)
        move = msg.created_move_ids
        self.assertEqual(move.move_type, "in_invoice")
        self.assertEqual(move.ref, "F001-00000123")

    def test_processes_xml_inside_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("factura.xml", SAMPLE_INVOICE_XML)
        msg = self._create_msg_with_attachments([("factura.zip", buf.getvalue())])
        msg._process_email_attachments()
        self.assertEqual(msg.state, "processed")
        self.assertEqual(len(msg.created_move_ids), 1)

    def test_no_attachments_marks_error(self):
        msg = self.Inbox.create({"name": "Vacío"})
        msg._process_email_attachments()
        self.assertEqual(msg.state, "error")
        self.assertIn("No se encontraron attachments", msg.processing_log)

    def test_non_xml_attachments_marks_error(self):
        msg = self._create_msg_with_attachments([("foto.jpg", b"\x89PNG fake")])
        msg._process_email_attachments()
        self.assertEqual(msg.state, "error")
        self.assertIn("Ningún attachment es XML", msg.processing_log)

    def test_invalid_xml_logs_error_but_keeps_record(self):
        msg = self._create_msg_with_attachments([("malo.xml", b"<not valid ubl/>")])
        msg._process_email_attachments()
        self.assertEqual(msg.state, "error")
        self.assertIn("malo.xml", msg.processing_log)
        self.assertFalse(msg.created_move_ids)

    def test_mixed_good_and_bad_xml(self):
        msg = self._create_msg_with_attachments(
            [
                ("bueno.xml", SAMPLE_INVOICE_XML),
                ("malo.xml", b"<garbage/>"),
            ]
        )
        msg._process_email_attachments()
        # Estado error porque algún fallo, pero el bueno SÍ creó move
        self.assertEqual(msg.state, "error")
        self.assertEqual(len(msg.created_move_ids), 1)

    def test_alias_record_created_from_message_new(self):
        """Simula la llamada del mailgateway: message_new con un msg_dict."""
        msg_dict = {
            "subject": "F001 del proveedor",
            "from": "billing@proveedor.com",
            "email_from": "billing@proveedor.com",
        }
        rec = self.Inbox.message_new(msg_dict)
        self.assertEqual(rec.email_from, "billing@proveedor.com")
        self.assertEqual(rec.subject, "F001 del proveedor")
        # Sin attachments → state error
        self.assertEqual(rec.state, "error")
