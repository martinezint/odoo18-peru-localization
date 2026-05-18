# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.tests.common import TransactionCase, tagged

from ..services.cdr_parser import CdrParseError, parse_cdr

CDR_ACCEPTED = b"""<?xml version="1.0" encoding="UTF-8"?>
<ar:ApplicationResponse
    xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>1</cbc:ID>
  <cbc:IssueDate>2026-05-18</cbc:IssueDate>
  <cac:DocumentResponse>
    <cac:Response>
      <cbc:ResponseCode>0</cbc:ResponseCode>
      <cbc:Description>La Factura numero F001-1, ha sido aceptada</cbc:Description>
    </cac:Response>
    <cac:DocumentReference>
      <cbc:ID>F001-1</cbc:ID>
    </cac:DocumentReference>
  </cac:DocumentResponse>
</ar:ApplicationResponse>
"""

CDR_OBSERVED = b"""<?xml version="1.0" encoding="UTF-8"?>
<ar:ApplicationResponse
    xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>1</cbc:ID>
  <cac:DocumentResponse>
    <cac:Response>
      <cbc:ResponseCode>2335</cbc:ResponseCode>
      <cbc:Description>La Factura ha sido aceptada con observaciones</cbc:Description>
    </cac:Response>
    <cac:DocumentReference>
      <cbc:ID>F001-2</cbc:ID>
    </cac:DocumentReference>
  </cac:DocumentResponse>
  <cbc:Note>El total de operaciones exoneradas no coincide</cbc:Note>
  <cbc:Note>Calculo del importe verificado</cbc:Note>
</ar:ApplicationResponse>
"""

CDR_REJECTED = b"""<?xml version="1.0" encoding="UTF-8"?>
<ar:ApplicationResponse
    xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>1</cbc:ID>
  <cac:DocumentResponse>
    <cac:Response>
      <cbc:ResponseCode>1032</cbc:ResponseCode>
      <cbc:Description>El RUC del emisor no esta activo</cbc:Description>
    </cac:Response>
    <cac:DocumentReference>
      <cbc:ID>F001-3</cbc:ID>
    </cac:DocumentReference>
  </cac:DocumentResponse>
</ar:ApplicationResponse>
"""


@tagged("post_install", "-at_install", "l10n_pe_edi_transport_sunat_soap")
class TestCdrParser(TransactionCase):
    # ─── Errores ─────────────────────────────────────────────────

    def test_empty_raises(self):
        with self.assertRaisesRegex(CdrParseError, "vacío"):
            parse_cdr(b"")

    def test_malformed_raises(self):
        with self.assertRaisesRegex(CdrParseError, "mal formado"):
            parse_cdr(b"<unclosed")

    # ─── CDR aceptado ────────────────────────────────────────────

    def test_accepted_code(self):
        cdr = parse_cdr(CDR_ACCEPTED)
        self.assertEqual(cdr.response_code, "0")
        self.assertIn("aceptada", cdr.description)
        self.assertEqual(cdr.document_ref, "F001-1")

    def test_accepted_flags(self):
        cdr = parse_cdr(CDR_ACCEPTED)
        self.assertTrue(cdr.is_accepted)
        self.assertFalse(cdr.is_observed)
        self.assertFalse(cdr.is_rejected)
        self.assertFalse(cdr.is_error)

    def test_accepted_no_notes(self):
        cdr = parse_cdr(CDR_ACCEPTED)
        self.assertEqual(cdr.notes, [])

    # ─── CDR observado (warnings) ────────────────────────────────

    def test_observed_code(self):
        cdr = parse_cdr(CDR_OBSERVED)
        self.assertEqual(cdr.response_code, "2335")

    def test_observed_flags(self):
        cdr = parse_cdr(CDR_OBSERVED)
        self.assertFalse(cdr.is_accepted)
        self.assertTrue(cdr.is_observed)
        self.assertFalse(cdr.is_rejected)
        self.assertFalse(cdr.is_error)

    def test_observed_collects_notes(self):
        cdr = parse_cdr(CDR_OBSERVED)
        self.assertEqual(len(cdr.notes), 2)
        self.assertIn("exoneradas", cdr.notes[0])

    # ─── CDR rechazado ───────────────────────────────────────────

    def test_rejected_code(self):
        cdr = parse_cdr(CDR_REJECTED)
        self.assertEqual(cdr.response_code, "1032")

    def test_rejected_flags(self):
        cdr = parse_cdr(CDR_REJECTED)
        self.assertFalse(cdr.is_accepted)
        self.assertFalse(cdr.is_observed)
        self.assertTrue(cdr.is_rejected)
        self.assertFalse(cdr.is_error)

    # ─── Code ranges (clasificación) ─────────────────────────────

    def test_code_range_classification(self):
        from ..services.cdr_parser import CdrResponse

        cases = [
            ("0", "accepted"),
            ("99", "neither"),  # < 100, no es nada conocido
            ("100", "rejected"),
            ("1999", "rejected"),
            ("2000", "observed"),
            ("3999", "observed"),
            ("4000", "error"),
            ("5000", "error"),
            ("abc", "neither"),  # no numérico
        ]
        for code, expected in cases:
            cdr = CdrResponse(response_code=code)
            if expected == "accepted":
                self.assertTrue(cdr.is_accepted, f"{code}")
            elif expected == "rejected":
                self.assertTrue(cdr.is_rejected, f"{code}")
            elif expected == "observed":
                self.assertTrue(cdr.is_observed, f"{code}")
            elif expected == "error":
                self.assertTrue(cdr.is_error, f"{code}")
            else:  # neither
                self.assertFalse(cdr.is_accepted)
                self.assertFalse(cdr.is_rejected)
                self.assertFalse(cdr.is_observed)
                self.assertFalse(cdr.is_error)
