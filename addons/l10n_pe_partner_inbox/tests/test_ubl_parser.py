# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.ubl_parser import UblParseError, parse_ubl

SAMPLE_INVOICE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
  <cbc:ID>F001-00000123</cbc:ID>
  <cbc:IssueDate>2026-05-15</cbc:IssueDate>
  <cbc:InvoiceTypeCode listID="0101">01</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>PEN</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyIdentification>
        <cbc:ID schemeID="6">20131312955</cbc:ID>
      </cac:PartyIdentification>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>SUPERINTENDENCIA NACIONAL DE ADUANAS</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyIdentification>
        <cbc:ID schemeID="6">20100047218</cbc:ID>
      </cac:PartyIdentification>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>BANCO DE CREDITO DEL PERU</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="PEN">36.00</cbc:TaxAmount>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="PEN">200.00</cbc:LineExtensionAmount>
    <cbc:PayableAmount currencyID="PEN">236.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="NIU">2.0</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="PEN">200.00</cbc:LineExtensionAmount>
    <cac:Item>
      <cbc:Description>Servicio de consultoría</cbc:Description>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="PEN">100.00</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>
</Invoice>
""".encode()

SAMPLE_CREDIT_NOTE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
            xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
            xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>FC01-00000001</cbc:ID>
  <cbc:IssueDate>2026-05-20</cbc:IssueDate>
  <cbc:CreditNoteTypeCode>07</cbc:CreditNoteTypeCode>
  <cbc:DocumentCurrencyCode>PEN</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID schemeID="6">20131312955</cbc:ID></cac:PartyIdentification>
      <cac:PartyLegalEntity><cbc:RegistrationName>SUPPLIER SAC</cbc:RegistrationName></cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:LegalMonetaryTotal>
    <cbc:PayableAmount currencyID="PEN">50.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:CreditNoteLine>
    <cbc:ID>1</cbc:ID>
    <cbc:CreditedQuantity unitCode="NIU">1.0</cbc:CreditedQuantity>
    <cbc:LineExtensionAmount currencyID="PEN">50.00</cbc:LineExtensionAmount>
    <cac:Item><cbc:Description>Devolución producto</cbc:Description></cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="PEN">50.00</cbc:PriceAmount></cac:Price>
  </cac:CreditNoteLine>
</CreditNote>
""".encode()


@tagged("post_install", "-at_install", "l10n_pe_partner_inbox")
class TestUblParser(TransactionCase):
    """Tests del parser puro — no toca Odoo ORM."""

    # ─── Errores de input ─────────────────────────────────────────

    def test_empty_xml_raises(self):
        with self.assertRaisesRegex(UblParseError, "vacío"):
            parse_ubl(b"")

    def test_malformed_xml_raises(self):
        with self.assertRaisesRegex(UblParseError, "mal formado"):
            parse_ubl(b"<not closed")

    # ─── Invoice típica ───────────────────────────────────────────

    def test_parse_invoice_document_number(self):
        parsed = parse_ubl(SAMPLE_INVOICE_XML)
        self.assertEqual(parsed.document_number, "F001-00000123")

    def test_parse_invoice_issue_date(self):
        parsed = parse_ubl(SAMPLE_INVOICE_XML)
        self.assertEqual(parsed.issue_date, date(2026, 5, 15))

    def test_parse_invoice_type_code(self):
        parsed = parse_ubl(SAMPLE_INVOICE_XML)
        self.assertEqual(parsed.document_type_code, "01")

    def test_parse_invoice_currency(self):
        parsed = parse_ubl(SAMPLE_INVOICE_XML)
        self.assertEqual(parsed.currency, "PEN")

    def test_parse_invoice_supplier(self):
        parsed = parse_ubl(SAMPLE_INVOICE_XML)
        self.assertEqual(parsed.supplier_ruc, "20131312955")
        self.assertEqual(parsed.supplier_name, "SUPERINTENDENCIA NACIONAL DE ADUANAS")

    def test_parse_invoice_customer(self):
        parsed = parse_ubl(SAMPLE_INVOICE_XML)
        self.assertEqual(parsed.customer_ruc, "20100047218")
        self.assertEqual(parsed.customer_name, "BANCO DE CREDITO DEL PERU")

    def test_parse_invoice_totals(self):
        parsed = parse_ubl(SAMPLE_INVOICE_XML)
        self.assertEqual(parsed.payable_amount, Decimal("236.00"))
        self.assertEqual(parsed.tax_amount, Decimal("36.00"))
        self.assertEqual(parsed.line_extension_amount, Decimal("200.00"))

    def test_parse_invoice_lines(self):
        parsed = parse_ubl(SAMPLE_INVOICE_XML)
        self.assertEqual(len(parsed.lines), 1)
        line = parsed.lines[0]
        self.assertEqual(line.description, "Servicio de consultoría")
        self.assertEqual(line.quantity, Decimal("2.0"))
        self.assertEqual(line.price_unit, Decimal("100.00"))
        self.assertEqual(line.line_extension_amount, Decimal("200.00"))

    # ─── Credit Note ──────────────────────────────────────────────

    def test_parse_credit_note(self):
        parsed = parse_ubl(SAMPLE_CREDIT_NOTE_XML)
        self.assertEqual(parsed.document_number, "FC01-00000001")
        self.assertEqual(parsed.document_type_code, "07")
        self.assertEqual(parsed.supplier_ruc, "20131312955")
        self.assertEqual(len(parsed.lines), 1)
        self.assertEqual(parsed.lines[0].description, "Devolución producto")
