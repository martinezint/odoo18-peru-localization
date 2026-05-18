# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from lxml import etree
from odoo.tests.common import TransactionCase, tagged

from ..services.rc_summary_builder import (
    NS_CAC,
    NS_CBC,
    NS_EXT,
    NS_SAC,
    NS_SUMMARY,
    RcLine,
    RcSummary,
    RcSummaryBuilder,
    RcSupplier,
)


def _make_minimal_summary(line_count=1):
    s = RcSummary(
        serie_number="RC-20260518-001",
        reference_date=date(2026, 5, 17),
        issue_date=date(2026, 5, 18),
        supplier=RcSupplier(ruc="20131312955", legal_name="EMISOR DEMO"),
    )
    for i in range(1, line_count + 1):
        s.lines.append(
            RcLine(
                line_id=i,
                serie="B001",
                start_number=str(i),
                end_number=str(i),
                total_amount=Decimal("118.00"),
                payable_amount=Decimal("100.00"),
                tax_amount=Decimal("18.00"),
            )
        )
    return s


@tagged("post_install", "-at_install", "l10n_pe_pos_edi")
class TestRcSummaryBuilder(TransactionCase):
    def setUp(self):
        super().setUp()
        self.builder = RcSummaryBuilder()
        self.summary = _make_minimal_summary(line_count=1)
        self.root = self.builder.build(self.summary)

    # ─── Estructura ───────────────────────────────────────────────

    def test_root_is_summary_documents(self):
        self.assertEqual(etree.QName(self.root.tag).localname, "SummaryDocuments")
        self.assertEqual(etree.QName(self.root.tag).namespace, NS_SUMMARY)

    def test_namespaces_declared_at_root(self):
        nsmap = self.root.nsmap
        self.assertEqual(nsmap.get("cbc"), NS_CBC)
        self.assertEqual(nsmap.get("cac"), NS_CAC)
        self.assertEqual(nsmap.get("ext"), NS_EXT)
        self.assertEqual(nsmap.get("sac"), NS_SAC)

    def test_extension_placeholder(self):
        path = f"{{{NS_EXT}}}UBLExtensions/{{{NS_EXT}}}UBLExtension/{{{NS_EXT}}}ExtensionContent"
        self.assertIsNotNone(self.root.find(path))

    def test_header_versions_and_id(self):
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}UBLVersionID"), "2.0")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}CustomizationID"), "1.1")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}ID"), "RC-20260518-001")

    def test_reference_date_is_boleta_date(self):
        # ReferenceDate = día de las boletas (no del envío)
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}ReferenceDate"), "2026-05-17")

    def test_issue_date_is_summary_date(self):
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}IssueDate"), "2026-05-18")

    # ─── Supplier ────────────────────────────────────────────────

    def test_supplier_ruc_and_account_id(self):
        ruc = self.root.findtext(
            f"{{{NS_CAC}}}AccountingSupplierParty/{{{NS_CBC}}}CustomerAssignedAccountID"
        )
        # AdditionalAccountID = 6 (RUC en cat 6)
        add_id = self.root.findtext(
            f"{{{NS_CAC}}}AccountingSupplierParty/{{{NS_CBC}}}AdditionalAccountID"
        )
        self.assertEqual(ruc, "20131312955")
        self.assertEqual(add_id, "6")

    def test_supplier_legal_name(self):
        name = self.root.findtext(
            f"{{{NS_CAC}}}AccountingSupplierParty/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyLegalEntity/{{{NS_CBC}}}RegistrationName"
        )
        self.assertEqual(name, "EMISOR DEMO")

    # ─── SummaryDocumentsLine ────────────────────────────────────

    def test_one_summary_line(self):
        lines = self.root.findall(f"{{{NS_SAC}}}SummaryDocumentsLine")
        self.assertEqual(len(lines), 1)

    def test_line_document_type_code_03(self):
        code = self.root.findtext(f"{{{NS_SAC}}}SummaryDocumentsLine/{{{NS_CBC}}}DocumentTypeCode")
        self.assertEqual(code, "03")

    def test_line_serie_and_range(self):
        serie = self.root.findtext(f"{{{NS_SAC}}}SummaryDocumentsLine/{{{NS_SAC}}}DocumentSerialID")
        start = self.root.findtext(
            f"{{{NS_SAC}}}SummaryDocumentsLine/{{{NS_SAC}}}StartDocumentNumberID"
        )
        end = self.root.findtext(
            f"{{{NS_SAC}}}SummaryDocumentsLine/{{{NS_SAC}}}EndDocumentNumberID"
        )
        self.assertEqual(serie, "B001")
        self.assertEqual(start, "1")
        self.assertEqual(end, "1")

    def test_line_total_amount(self):
        amt = self.root.find(f"{{{NS_SAC}}}SummaryDocumentsLine/{{{NS_SAC}}}TotalAmount")
        self.assertEqual(amt.text, "118.00")
        self.assertEqual(amt.get("currencyID"), "PEN")

    def test_line_billing_payment_with_instruction_01(self):
        bp_path = f"{{{NS_SAC}}}SummaryDocumentsLine/{{{NS_SAC}}}BillingPayments"
        paid = self.root.findtext(f"{bp_path}/{{{NS_CBC}}}PaidAmount")
        instr = self.root.findtext(f"{bp_path}/{{{NS_CBC}}}InstructionID")
        self.assertEqual(paid, "100.00")
        self.assertEqual(instr, "01")

    def test_line_tax_total_igv(self):
        tt_path = f"{{{NS_SAC}}}SummaryDocumentsLine/{{{NS_CAC}}}TaxTotal"
        tax = self.root.findtext(f"{tt_path}/{{{NS_CBC}}}TaxAmount")
        scheme_id = self.root.findtext(
            f"{tt_path}/{{{NS_CAC}}}TaxSubtotal/{{{NS_CAC}}}TaxCategory"
            f"/{{{NS_CAC}}}TaxScheme/{{{NS_CBC}}}ID"
        )
        self.assertEqual(tax, "18.00")
        self.assertEqual(scheme_id, "1000")

    # ─── Multiples líneas ────────────────────────────────────────

    def test_multiple_lines(self):
        summary = _make_minimal_summary(line_count=5)
        root = self.builder.build(summary)
        self.assertEqual(
            len(root.findall(f"{{{NS_SAC}}}SummaryDocumentsLine")),
            5,
        )

    # ─── Serialization ────────────────────────────────────────────

    def test_serialization_is_valid_xml(self):
        xml = self.builder.build_xml_bytes(self.summary)
        self.assertTrue(xml.startswith(b"<?xml"))
        parsed = etree.fromstring(xml)
        self.assertEqual(etree.QName(parsed.tag).localname, "SummaryDocuments")
