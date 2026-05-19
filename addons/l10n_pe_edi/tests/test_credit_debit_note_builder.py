# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date, time
from decimal import Decimal

from lxml import etree
from odoo.tests.common import TransactionCase, tagged

from ..services.ubl_builder import InvoiceLine, Party
from ..services.ubl_credit_debit_note_builder import (
    NS_CREDIT_NOTE,
    NS_DEBIT_NOTE,
    BillingReference,
    CreditDebitNote,
    UblCreditDebitNoteBuilder,
)


def _build_note(*, is_credit: bool = True):
    return CreditDebitNote(
        serie_number="FC01-1" if is_credit else "FD01-1",
        issue_date=date(2026, 5, 18),
        issue_time=time(10, 30, 0),
        is_credit=is_credit,
        reason_code="01",
        reason_description="ANULACIÓN DE LA OPERACIÓN",
        billing_reference=BillingReference(serie_number="F001-100", doc_type_code="01"),
        currency_code="PEN",
        supplier=Party(ruc="20131312955", doc_type_code="6", legal_name="EMISOR SAC"),
        customer=Party(ruc="20100047218", doc_type_code="6", legal_name="CLIENTE SA"),
        lines=[
            InvoiceLine(
                line_id=1,
                description="Servicio cancelado",
                quantity=Decimal("1"),
                unit_code="NIU",
                unit_price=Decimal("100.00"),
                line_extension_amount=Decimal("100.00"),
                igv_amount=Decimal("18.00"),
                igv_percentage=Decimal("18"),
            )
        ],
        total_igv=Decimal("18.00"),
        total_taxed=Decimal("100.00"),
        total_line_extension=Decimal("100.00"),
        total_payable=Decimal("118.00"),
        total_tax_exclusive=Decimal("100.00"),
        total_tax_inclusive=Decimal("118.00"),
    )


@tagged("post_install", "-at_install", "l10n_pe_edi")
class TestCreditNoteBuilder(TransactionCase):
    """Nota de Crédito (07) UBL builder."""

    def test_root_is_credit_note(self):
        root = UblCreditDebitNoteBuilder().build(_build_note(is_credit=True))
        self.assertEqual(root.tag, f"{{{NS_CREDIT_NOTE}}}CreditNote")

    def test_billing_reference_points_to_original(self):
        xml = UblCreditDebitNoteBuilder().build_xml_bytes(_build_note(is_credit=True))
        tree = etree.fromstring(xml)
        ns = {
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }
        ref_id = tree.findtext(".//cac:InvoiceDocumentReference/cbc:ID", namespaces=ns)
        self.assertEqual(ref_id, "F001-100")
        ref_type = tree.findtext(
            ".//cac:InvoiceDocumentReference/cbc:DocumentTypeCode", namespaces=ns
        )
        self.assertEqual(ref_type, "01")

    def test_discrepancy_response_present(self):
        xml = UblCreditDebitNoteBuilder().build_xml_bytes(_build_note(is_credit=True))
        tree = etree.fromstring(xml)
        ns = {
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }
        dr = tree.find(".//cac:DiscrepancyResponse", namespaces=ns)
        self.assertIsNotNone(dr)
        self.assertEqual(dr.findtext("cbc:ResponseCode", namespaces=ns), "01")
        self.assertEqual(dr.findtext("cbc:ReferenceID", namespaces=ns), "F001-100")

    def test_uses_credit_note_line_tag(self):
        xml = UblCreditDebitNoteBuilder().build_xml_bytes(_build_note(is_credit=True))
        tree = etree.fromstring(xml)
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}
        lines = tree.findall(".//cac:CreditNoteLine", namespaces=ns)
        self.assertEqual(len(lines), 1)

    def test_uses_legal_monetary_total_for_credit(self):
        xml = UblCreditDebitNoteBuilder().build_xml_bytes(_build_note(is_credit=True))
        tree = etree.fromstring(xml)
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}
        lmt = tree.find(".//cac:LegalMonetaryTotal", namespaces=ns)
        self.assertIsNotNone(lmt)


@tagged("post_install", "-at_install", "l10n_pe_edi")
class TestDebitNoteBuilder(TransactionCase):
    """Nota de Débito (08) UBL builder."""

    def test_root_is_debit_note(self):
        root = UblCreditDebitNoteBuilder().build(_build_note(is_credit=False))
        self.assertEqual(root.tag, f"{{{NS_DEBIT_NOTE}}}DebitNote")

    def test_uses_debit_note_line_tag(self):
        xml = UblCreditDebitNoteBuilder().build_xml_bytes(_build_note(is_credit=False))
        tree = etree.fromstring(xml)
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}
        lines = tree.findall(".//cac:DebitNoteLine", namespaces=ns)
        self.assertEqual(len(lines), 1)

    def test_uses_requested_monetary_total_for_debit(self):
        xml = UblCreditDebitNoteBuilder().build_xml_bytes(_build_note(is_credit=False))
        tree = etree.fromstring(xml)
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}
        rmt = tree.find(".//cac:RequestedMonetaryTotal", namespaces=ns)
        self.assertIsNotNone(rmt)

    def test_discrepancy_uses_catalog_10_for_debit(self):
        xml = UblCreditDebitNoteBuilder().build_xml_bytes(_build_note(is_credit=False))
        tree = etree.fromstring(xml)
        ns = {
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }
        rc = tree.find(".//cac:DiscrepancyResponse/cbc:ResponseCode", namespaces=ns)
        # Debe referenciar catalogo 10 (motivos ND), no catalogo 09 (NC)
        self.assertIn("catalogo10", rc.get("listURI", ""))
