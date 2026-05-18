# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Tests del flujo SOAP async: sendSummary + getStatus.

Patrón idéntico al test del sendBill sync: mocked zeep client, sin red real.
"""

import io
import zipfile
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from ..services.sunat_soap import SunatBillService, SunatSoapError


def _mk_cdr_zip(filename: str, cdr_xml: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"R-{filename}", cdr_xml)
    return buf.getvalue()


CDR_RC_ACCEPTED = b"""<?xml version="1.0"?>
<ar:ApplicationResponse
    xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cac:DocumentResponse><cac:Response>
    <cbc:ResponseCode>0</cbc:ResponseCode>
    <cbc:Description>RC aceptado</cbc:Description>
  </cac:Response></cac:DocumentResponse>
</ar:ApplicationResponse>
"""


@tagged("post_install", "-at_install", "l10n_pe_edi_transport_sunat_soap")
class TestSendSummary(TransactionCase):
    """sendSummary devuelve un ticket (string)."""

    def _new_client(self):
        return SunatBillService(
            ruc="20131312955",
            sol_user="MODDATOS",
            sol_password="MODDATOS",
        )

    def _patched_client(self, fake_client):
        return patch.object(
            type(self._new_client()),
            "client",
            new_callable=lambda: property(lambda self: fake_client),
        )

    def test_send_summary_returns_ticket(self):
        client = self._new_client()
        fake_service = MagicMock()
        fake_service.sendSummary.return_value = "1234567890"
        fake_client = MagicMock()
        fake_client.service = fake_service

        with self._patched_client(fake_client):
            ticket = client.send_summary(
                "20131312955-RC-20260518-001.zip", b"zip-bytes",
            )
        self.assertEqual(ticket, "1234567890")
        # Verifica que llamó sendSummary con los args correctos
        fake_service.sendSummary.assert_called_once_with(
            fileName="20131312955-RC-20260518-001.zip",
            contentFile=b"zip-bytes",
        )

    def test_send_summary_empty_ticket_raises(self):
        client = self._new_client()
        fake_service = MagicMock()
        fake_service.sendSummary.return_value = ""
        fake_client = MagicMock()
        fake_client.service = fake_service

        with self._patched_client(fake_client):
            with self.assertRaises(SunatSoapError) as ctx:
                client.send_summary("x.zip", b"x")
        self.assertEqual(ctx.exception.fault_code, "EMPTY_TICKET")

    def test_send_summary_fault_raises(self):
        from zeep.exceptions import Fault
        client = self._new_client()
        fake_service = MagicMock()
        fake_service.sendSummary.side_effect = Fault(
            "0104: Clave incorrecta", code="0104"
        )
        fake_client = MagicMock()
        fake_client.service = fake_service

        with self._patched_client(fake_client):
            with self.assertRaises(SunatSoapError) as ctx:
                client.send_summary("x.zip", b"x")
        self.assertIn("0104", str(ctx.exception))

    def test_send_summary_transport_error_raises(self):
        from zeep.exceptions import TransportError
        client = self._new_client()
        fake_service = MagicMock()
        fake_service.sendSummary.side_effect = TransportError("Connection refused")
        fake_client = MagicMock()
        fake_client.service = fake_service

        with self._patched_client(fake_client):
            with self.assertRaises(SunatSoapError):
                client.send_summary("x.zip", b"x")


@tagged("post_install", "-at_install", "l10n_pe_edi_transport_sunat_soap")
class TestGetStatusAsync(TransactionCase):
    """getStatus devuelve estado del ticket — '98' en proceso, '0' listo con CDR."""

    def _new_client(self):
        return SunatBillService(
            ruc="20131312955",
            sol_user="MODDATOS",
            sol_password="MODDATOS",
        )

    def _patched_client(self, fake_client):
        return patch.object(
            type(self._new_client()),
            "client",
            new_callable=lambda: property(lambda self: fake_client),
        )

    def _make_zeep_status_response(self, status_code, content=None):
        resp = MagicMock()
        resp.statusCode = status_code
        resp.content = content
        return resp

    def test_status_in_process_returns_98(self):
        client = self._new_client()
        fake_service = MagicMock()
        fake_service.getStatus.return_value = self._make_zeep_status_response("98")
        fake_client = MagicMock()
        fake_client.service = fake_service

        with self._patched_client(fake_client):
            result = client.get_status_async("ticket-123")
        self.assertEqual(result["status_code"], "98")
        self.assertEqual(result["cdr_bytes"], b"")

    def test_status_done_returns_cdr_bytes(self):
        client = self._new_client()
        cdr_zip = _mk_cdr_zip("20131312955-RC-20260518-001.xml", CDR_RC_ACCEPTED)
        fake_service = MagicMock()
        fake_service.getStatus.return_value = self._make_zeep_status_response(
            "0", content=cdr_zip,
        )
        fake_client = MagicMock()
        fake_client.service = fake_service

        with self._patched_client(fake_client):
            result = client.get_status_async("ticket-123")
        self.assertEqual(result["status_code"], "0")
        self.assertEqual(result["cdr_bytes"], CDR_RC_ACCEPTED)

    def test_status_error_code(self):
        client = self._new_client()
        fake_service = MagicMock()
        fake_service.getStatus.return_value = self._make_zeep_status_response("99")
        fake_client = MagicMock()
        fake_client.service = fake_service

        with self._patched_client(fake_client):
            result = client.get_status_async("ticket-bad")
        self.assertEqual(result["status_code"], "99")
        self.assertEqual(result["cdr_bytes"], b"")

    def test_status_fault_raises(self):
        from zeep.exceptions import Fault
        client = self._new_client()
        fake_service = MagicMock()
        fake_service.getStatus.side_effect = Fault("invalid ticket", code="0114")
        fake_client = MagicMock()
        fake_client.service = fake_service

        with self._patched_client(fake_client):
            with self.assertRaises(SunatSoapError):
                client.get_status_async("invalid")

    def test_status_dict_response_supported(self):
        """zeep puede devolver dict en lugar de struct; ambos deben funcionar."""
        client = self._new_client()
        fake_service = MagicMock()
        fake_service.getStatus.return_value = {"statusCode": "98", "content": None}
        fake_client = MagicMock()
        fake_client.service = fake_service

        with self._patched_client(fake_client):
            result = client.get_status_async("ticket-123")
        self.assertEqual(result["status_code"], "98")


@tagged("post_install", "-at_install", "l10n_pe_edi_transport_sunat_soap")
class TestL10nPeEdiDocumentSummaryFields(TransactionCase):
    """Verifica que los fields nuevos en l10n.pe.edi.document están disponibles."""

    def test_summary_fields_exist(self):
        Doc = self.env["l10n.pe.edi.document"]
        self.assertIn("sunat_summary_ticket", Doc._fields)
        self.assertIn("sunat_summary_status_code", Doc._fields)
        self.assertIn("sunat_summary_last_check_at", Doc._fields)

    def test_summary_status_selection_codes(self):
        Doc = self.env["l10n.pe.edi.document"]
        field = Doc._fields["sunat_summary_status_code"]
        codes = [v[0] for v in field.selection]
        self.assertIn("0", codes)
        self.assertIn("98", codes)
        self.assertIn("99", codes)
        self.assertIn("90", codes)
