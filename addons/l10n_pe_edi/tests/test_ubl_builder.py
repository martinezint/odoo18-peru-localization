# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Tests del UBL builder: estructura, namespaces, valores.

No tocan Odoo ORM ni la firma — solo verifican que el XML resultante tiene
los elementos que SUNAT espera, en los namespaces correctos.
"""

from datetime import date, time
from decimal import Decimal

from lxml import etree
from odoo.tests.common import TransactionCase, tagged

from ..services.ubl_builder import (
    NS_CAC,
    NS_CBC,
    NS_DS,
    NS_EXT,
    Invoice,
    InvoiceLine,
    Party,
    UblInvoiceBuilder,
)


def _make_minimal_invoice() -> Invoice:
    inv = Invoice(
        serie_number="F001-1",
        issue_date=date(2026, 5, 15),
        issue_time=time(10, 30, 0),
        currency_code="PEN",
        note_amount_in_words="SON CIENTO DIECIOCHO CON 00/100 SOLES",
        supplier=Party(
            ruc="20131312955",
            doc_type_code="6",
            legal_name="SUNAT",
            address_street="AV. GARCILASO DE LA VEGA 1472",
            address_district="LIMA",
            address_city="LIMA",
            ubigeo="150101",
        ),
        customer=Party(
            ruc="20100047218",
            doc_type_code="6",
            legal_name="BANCO DE CREDITO DEL PERU",
        ),
    )
    inv.lines.append(
        InvoiceLine(
            line_id=1,
            description="Servicio de consultoría",
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            line_extension_amount=Decimal("100.00"),
            igv_amount=Decimal("18.00"),
            igv_affectation_code="10",
            igv_percentage=Decimal("18"),
        )
    )
    inv.total_line_extension = Decimal("100.00")
    inv.total_taxed = Decimal("100.00")
    inv.total_igv = Decimal("18.00")
    inv.total_tax_exclusive = Decimal("100.00")
    inv.total_tax_inclusive = Decimal("118.00")
    inv.total_payable = Decimal("118.00")
    return inv


@tagged("post_install", "-at_install", "l10n_pe_edi")
class TestUblBuilder(TransactionCase):
    def setUp(self):
        super().setUp()
        self.builder = UblInvoiceBuilder()
        self.invoice = _make_minimal_invoice()
        self.root = self.builder.build(self.invoice)

    # ─── Estructura ───────────────────────────────────────────────

    def test_root_is_invoice_in_correct_namespace(self):
        self.assertEqual(etree.QName(self.root.tag).localname, "Invoice")
        self.assertEqual(
            etree.QName(self.root.tag).namespace,
            "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        )

    def test_has_ubl_extensions_with_signature_placeholder(self):
        path = f"{{{NS_EXT}}}UBLExtensions/{{{NS_EXT}}}UBLExtension/{{{NS_EXT}}}ExtensionContent"
        ext = self.root.find(path)
        self.assertIsNotNone(ext, "Falta placeholder de firma ext:ExtensionContent")
        # Placeholder está vacío (para firmar después)
        self.assertEqual(len(list(ext)), 0)

    def test_has_required_header_fields(self):
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}UBLVersionID"), "2.1")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}CustomizationID"), "2.0")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}ID"), "F001-1")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}IssueDate"), "2026-05-15")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}DocumentCurrencyCode"), "PEN")

    def test_invoice_type_code_has_list_id(self):
        type_el = self.root.find(f"{{{NS_CBC}}}InvoiceTypeCode")
        self.assertEqual(type_el.text, "01")
        self.assertEqual(type_el.get("listID"), "0101")

    def test_note_with_language_locale_id(self):
        note = self.root.find(f"{{{NS_CBC}}}Note")
        self.assertEqual(note.text, "SON CIENTO DIECIOCHO CON 00/100 SOLES")
        self.assertEqual(note.get("languageLocaleID"), "1000")

    # ─── Supplier / Customer ──────────────────────────────────────

    def test_supplier_ruc_and_doc_type(self):
        sup_id = self.root.find(
            f"{{{NS_CAC}}}AccountingSupplierParty"
            f"/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyIdentification"
            f"/{{{NS_CBC}}}ID"
        )
        self.assertEqual(sup_id.text, "20131312955")
        self.assertEqual(sup_id.get("schemeID"), "6")  # RUC
        self.assertEqual(sup_id.get("schemeAgencyName"), "PE:SUNAT")

    def test_supplier_legal_name(self):
        name = self.root.findtext(
            f"{{{NS_CAC}}}AccountingSupplierParty"
            f"/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyLegalEntity"
            f"/{{{NS_CBC}}}RegistrationName"
        )
        self.assertEqual(name, "SUNAT")

    def test_supplier_address_ubigeo(self):
        ubigeo = self.root.findtext(
            f"{{{NS_CAC}}}AccountingSupplierParty"
            f"/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PostalAddress"
            f"/{{{NS_CBC}}}ID"
        )
        self.assertEqual(ubigeo, "150101")

    def test_customer_ruc(self):
        cust_id = self.root.findtext(
            f"{{{NS_CAC}}}AccountingCustomerParty"
            f"/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyIdentification"
            f"/{{{NS_CBC}}}ID"
        )
        self.assertEqual(cust_id, "20100047218")

    # ─── TaxTotal ─────────────────────────────────────────────────

    def test_global_tax_total_igv_amount(self):
        amt = self.root.findtext(f"{{{NS_CAC}}}TaxTotal/{{{NS_CBC}}}TaxAmount")
        self.assertEqual(amt, "18.00")

    def test_tax_scheme_is_igv(self):
        scheme_id = self.root.findtext(
            f"{{{NS_CAC}}}TaxTotal/{{{NS_CAC}}}TaxSubtotal"
            f"/{{{NS_CAC}}}TaxCategory/{{{NS_CAC}}}TaxScheme/{{{NS_CBC}}}ID"
        )
        self.assertEqual(scheme_id, "1000")

    # ─── LegalMonetaryTotal ───────────────────────────────────────

    def test_payable_amount(self):
        amt = self.root.findtext(f"{{{NS_CAC}}}LegalMonetaryTotal/{{{NS_CBC}}}PayableAmount")
        self.assertEqual(amt, "118.00")

    def test_line_extension_amount_total(self):
        amt = self.root.findtext(f"{{{NS_CAC}}}LegalMonetaryTotal/{{{NS_CBC}}}LineExtensionAmount")
        self.assertEqual(amt, "100.00")

    # ─── InvoiceLine ──────────────────────────────────────────────

    def test_one_invoice_line(self):
        lines = self.root.findall(f"{{{NS_CAC}}}InvoiceLine")
        self.assertEqual(len(lines), 1)

    def test_line_quantity_and_unit(self):
        qty_el = self.root.find(f"{{{NS_CAC}}}InvoiceLine/{{{NS_CBC}}}InvoicedQuantity")
        self.assertEqual(qty_el.text, "1.000")
        self.assertEqual(qty_el.get("unitCode"), "NIU")

    def test_line_item_description(self):
        desc = self.root.findtext(
            f"{{{NS_CAC}}}InvoiceLine/{{{NS_CAC}}}Item/{{{NS_CBC}}}Description"
        )
        self.assertEqual(desc, "Servicio de consultoría")

    # ─── Serialization ────────────────────────────────────────────

    def test_serialization_is_well_formed_xml(self):
        xml_bytes = self.builder.build_xml_bytes(self.invoice)
        self.assertTrue(xml_bytes.startswith(b"<?xml"))
        parsed = etree.fromstring(xml_bytes)
        self.assertEqual(etree.QName(parsed.tag).localname, "Invoice")

    def test_namespaces_declared_at_root(self):
        # cbc, cac, ext, ds, xsi deben declararse en el root
        nsmap = self.root.nsmap
        self.assertEqual(nsmap.get("cbc"), NS_CBC)
        self.assertEqual(nsmap.get("cac"), NS_CAC)
        self.assertEqual(nsmap.get("ext"), NS_EXT)
        self.assertEqual(nsmap.get("ds"), NS_DS)
