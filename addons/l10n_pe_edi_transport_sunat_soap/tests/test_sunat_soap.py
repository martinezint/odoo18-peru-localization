# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Tests del cliente SOAP SUNAT — todo el I/O mockeado (no toca red)."""

import io
import zipfile
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from ..services.sunat_soap import (
    ENDPOINTS,
    SunatBillService,
    SunatSoapError,
)


def _make_cdr_zip(xml_filename: str, cdr_xml: bytes) -> bytes:
    """Crea un ZIP como el que devuelve SUNAT (con R-... dentro)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"R-{xml_filename}", cdr_xml)
    return buf.getvalue()


CDR_ACCEPTED_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ar:ApplicationResponse
    xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>1</cbc:ID>
  <cac:DocumentResponse>
    <cac:Response>
      <cbc:ResponseCode>0</cbc:ResponseCode>
      <cbc:Description>Aceptado</cbc:Description>
    </cac:Response>
  </cac:DocumentResponse>
</ar:ApplicationResponse>
"""


@tagged("post_install", "-at_install", "l10n_pe_edi_transport_sunat_soap")
class TestSunatSoapClient(TransactionCase):
    # ─── Construcción ────────────────────────────────────────────

    def test_init_uses_beta_endpoint_by_default(self):
        c = SunatBillService(ruc="20131312955", sol_user="MODDATOS", sol_password="MODDATOS")
        self.assertEqual(c.endpoint, ENDPOINTS["beta"])
        self.assertEqual(c.username, "20131312955MODDATOS")

    def test_init_production_endpoint(self):
        c = SunatBillService(
            ruc="20131312955", sol_user="USER", sol_password="X", environment="production"
        )
        self.assertEqual(c.endpoint, ENDPOINTS["production"])

    def test_init_invalid_environment_raises(self):
        with self.assertRaisesRegex(ValueError, "environment"):
            SunatBillService(ruc="R", sol_user="U", sol_password="P", environment="staging")

    def test_init_endpoint_override(self):
        c = SunatBillService(
            ruc="R", sol_user="U", sol_password="P", endpoint_override="http://localhost/test"
        )
        self.assertEqual(c.endpoint, "http://localhost/test")

    # ─── ZIP helpers ─────────────────────────────────────────────

    def test_zip_xml_contains_single_entry(self):
        zip_bytes = SunatBillService.zip_xml("test.xml", b"<root/>")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            self.assertEqual(zf.namelist(), ["test.xml"])
            self.assertEqual(zf.read("test.xml"), b"<root/>")

    def test_extract_cdr_finds_r_prefixed_xml(self):
        zip_bytes = _make_cdr_zip("20131312955-01-F001-1.xml", CDR_ACCEPTED_XML)
        cdr = SunatBillService.extract_cdr_from_zip(zip_bytes)
        self.assertEqual(cdr, CDR_ACCEPTED_XML)

    def test_extract_cdr_falls_back_to_first_xml(self):
        """Si no hay R-... el extractor toma el primer XML."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("respuesta.xml", b"<x/>")
        cdr = SunatBillService.extract_cdr_from_zip(buf.getvalue())
        self.assertEqual(cdr, b"<x/>")

    def test_extract_cdr_empty_zip_raises(self):
        with self.assertRaisesRegex(SunatSoapError, "vacía"):
            SunatBillService.extract_cdr_from_zip(b"")

    def test_extract_cdr_zip_without_xml_raises(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("README.txt", b"hello")
        with self.assertRaisesRegex(SunatSoapError, "no contiene CDR"):
            SunatBillService.extract_cdr_from_zip(buf.getvalue())

    # ─── send_bill (zeep mockeado) ───────────────────────────────

    def test_send_bill_returns_cdr_bytes(self):
        client = SunatBillService(ruc="20131312955", sol_user="MODDATOS", sol_password="MODDATOS")
        # Mock interno: el response es el ZIP CDR
        cdr_zip = _make_cdr_zip("20131312955-01-F001-1.xml", CDR_ACCEPTED_XML)
        fake_service = MagicMock()
        fake_service.sendBill.return_value = cdr_zip
        fake_client = MagicMock()
        fake_client.service = fake_service

        with patch.object(
            type(client),
            "client",
            new_callable=lambda: property(lambda self: fake_client),
        ):
            cdr_bytes = client.send_bill("20131312955-01-F001-1.zip", b"fake-zip-content")
        self.assertEqual(cdr_bytes, CDR_ACCEPTED_XML)
        fake_service.sendBill.assert_called_once_with(
            fileName="20131312955-01-F001-1.zip",
            contentFile=b"fake-zip-content",
        )

    def test_send_bill_zeep_fault_raises_sunat_error(self):
        from zeep.exceptions import Fault

        client = SunatBillService(ruc="20131312955", sol_user="X", sol_password="X")
        fake_service = MagicMock()
        fault = Fault("0104: Clave incorrecta", code="0104")
        fake_service.sendBill.side_effect = fault
        fake_client = MagicMock()
        fake_client.service = fake_service

        with patch.object(
            type(client),
            "client",
            new_callable=lambda: property(lambda self: fake_client),
        ):
            with self.assertRaises(SunatSoapError) as ctx:
                client.send_bill("x.zip", b"x")
        # zeep's Fault.code may be the raw code or a complex namespace QName
        self.assertIn("0104", str(ctx.exception))

    def test_send_bill_transport_error_raises(self):
        from zeep.exceptions import TransportError

        client = SunatBillService(ruc="20131312955", sol_user="X", sol_password="X")
        fake_service = MagicMock()
        fake_service.sendBill.side_effect = TransportError("Connection refused", status_code=500)
        fake_client = MagicMock()
        fake_client.service = fake_service

        with patch.object(
            type(client),
            "client",
            new_callable=lambda: property(lambda self: fake_client),
        ):
            with self.assertRaises(SunatSoapError) as ctx:
                client.send_bill("x.zip", b"x")
        self.assertIn("TRANSPORT", str(ctx.exception))


@tagged("post_install", "-at_install", "l10n_pe_edi_transport_sunat_soap")
class TestAccountMoveSendAction(TransactionCase):
    """End-to-end: action_l10n_pe_edi_send_sunat con zeep mockeado.

    No requiere chart de cuentas — solo crea un EDI document a mano.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Transport Co",
                "country_id": cls.pe.id,
                "vat": "20131312955",
                "l10n_pe_edi_sol_user": "MODDATOS",
                "l10n_pe_edi_sol_password": "MODDATOS",
                "l10n_pe_edi_environment": "beta",
            }
        )
        # Necesario para que account.move.create() encuentre journals + accounts.
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)

    def _make_signed_doc(self):
        """Crea un account.move + EDI document en estado 'signed' (sin pasar por _post)."""
        partner = self.env["res.partner"].create(
            {
                "name": "Client Co",
                "country_id": self.pe.id,
            }
        )
        # Move "sintético" — no validamos contabilidad, solo trazabilidad EDI
        move = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": partner.id,
                    "company_id": self.company.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Test",
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
                "name": "20131312955-01-F001-1.xml",
                "state": "signed",
                "xml_signed": b"<fake/>".__class__(
                    __import__("base64").b64encode(b"<fake-signed-xml/>")
                ),
            }
        )
        move.l10n_pe_edi_document_id = doc.id
        return move, doc

    def test_send_updates_doc_to_accepted_on_code_0(self):
        move, doc = self._make_signed_doc()
        cdr_zip = _make_cdr_zip("20131312955-01-F001-1.xml", CDR_ACCEPTED_XML)
        fake_service = MagicMock()
        fake_service.sendBill.return_value = cdr_zip
        fake_client = MagicMock()
        fake_client.service = fake_service

        with patch(
            "odoo.addons.l10n_pe_edi_transport_sunat_soap.services.sunat_soap."
            "SunatBillService.client",
            new_callable=lambda: property(lambda self: fake_client),
        ):
            move.action_l10n_pe_edi_send_sunat()

        doc.invalidate_recordset()
        self.assertEqual(doc.state, "accepted")
        self.assertEqual(doc.sunat_response_code, "0")
        self.assertIn("Aceptado", doc.sunat_response_description)
        self.assertTrue(doc.sunat_cdr)
        self.assertTrue(doc.sunat_sent_at)

    def test_send_updates_doc_to_rejected_on_4_digit_code(self):
        move, doc = self._make_signed_doc()
        cdr_rejected = b"""<?xml version="1.0"?>
<ar:ApplicationResponse xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cac:DocumentResponse><cac:Response>
    <cbc:ResponseCode>1032</cbc:ResponseCode>
    <cbc:Description>RUC no activo</cbc:Description>
  </cac:Response></cac:DocumentResponse>
</ar:ApplicationResponse>"""
        cdr_zip = _make_cdr_zip("20131312955-01-F001-1.xml", cdr_rejected)
        fake_service = MagicMock()
        fake_service.sendBill.return_value = cdr_zip
        fake_client = MagicMock()
        fake_client.service = fake_service

        with patch(
            "odoo.addons.l10n_pe_edi_transport_sunat_soap.services.sunat_soap."
            "SunatBillService.client",
            new_callable=lambda: property(lambda self: fake_client),
        ):
            move.action_l10n_pe_edi_send_sunat()

        doc.invalidate_recordset()
        self.assertEqual(doc.state, "rejected")
        self.assertEqual(doc.sunat_response_code, "1032")
        self.assertEqual(doc.error_message, "RUC no activo")

    def test_send_idempotent_when_already_accepted(self):
        move, doc = self._make_signed_doc()
        doc.state = "accepted"
        # No mock — si llama send_bill, fallaría por sin red.
        result = move._l10n_pe_edi_send_sunat_one()
        self.assertEqual(result, doc)
        # Confirma que state no cambió y no se llamó al servicio.
        self.assertEqual(doc.state, "accepted")
