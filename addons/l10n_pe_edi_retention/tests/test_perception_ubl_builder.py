# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from lxml import etree
from odoo.tests.common import TransactionCase, tagged

from ..services.perception_ubl_builder import (
    NS_CBC,
    NS_PERCEPTION,
    NS_SAC,
    Perception,
    PerceptionDocument,
    PerceptionParty,
    PerceptionUblBuilder,
)


def _make_minimal_perception():
    per = Perception(
        serie_number="P001-1",
        issue_date=date(2026, 5, 18),
        note_amount_in_words="SON VEINTITRES CON 60/100 SOLES",
        agent=PerceptionParty(
            ruc="20131312955",
            doc_type_code="6",
            legal_name="AGENTE PERCEPTOR",
        ),
        receiver=PerceptionParty(
            ruc="20100047218",
            doc_type_code="6",
            legal_name="CLIENTE PERCIBIDO",
        ),
        regime_code="01",
        regime_percent=Decimal("2"),
    )
    doc = PerceptionDocument(
        doc_type_code="01",
        serie_number="F001-456",
        issue_date=date(2026, 5, 15),
        total_amount=Decimal("1180.00"),
        currency_code="PEN",
        paid_amount=Decimal("1180.00"),
        paid_date=date(2026, 5, 18),
        perception_amount=Decimal("23.60"),
        perception_date=date(2026, 5, 18),
        total_cashed=Decimal("1203.60"),
    )
    per.documents.append(doc)
    per.total_perception_amount = Decimal("23.60")
    per.total_cashed = Decimal("1203.60")
    return per


@tagged("post_install", "-at_install", "l10n_pe_edi_retention")
class TestPerceptionUblBuilder(TransactionCase):
    def setUp(self):
        super().setUp()
        self.builder = PerceptionUblBuilder()
        self.per = _make_minimal_perception()
        self.root = self.builder.build(self.per)

    def test_root_is_perception(self):
        self.assertEqual(etree.QName(self.root.tag).localname, "Perception")
        self.assertEqual(etree.QName(self.root.tag).namespace, NS_PERCEPTION)

    def test_header_versions(self):
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}UBLVersionID"), "2.0")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}CustomizationID"), "1.0")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}ID"), "P001-1")

    def test_sunat_perception_system_and_percent(self):
        self.assertEqual(self.root.findtext(f"{{{NS_SAC}}}SUNATPerceptionSystemCode"), "01")
        self.assertEqual(self.root.findtext(f"{{{NS_SAC}}}SUNATPerceptionPercent"), "2")

    def test_total_invoice_amount(self):
        amt = self.root.find(f"{{{NS_CBC}}}TotalInvoiceAmount")
        self.assertEqual(amt.text, "23.60")

    def test_total_paid_is_total_cashed(self):
        amt = self.root.find(f"{{{NS_CBC}}}TotalPaid")
        self.assertEqual(amt.text, "1203.60")

    def test_perception_document_reference_present(self):
        docs = self.root.findall(f"{{{NS_SAC}}}SUNATPerceptionDocumentReference")
        self.assertEqual(len(docs), 1)

    def test_document_perception_info(self):
        info = (
            f"{{{NS_SAC}}}SUNATPerceptionDocumentReference/{{{NS_SAC}}}SUNATPerceptionInformation"
        )
        amt = self.root.findtext(f"{info}/{{{NS_SAC}}}SUNATPerceptionAmount")
        date_txt = self.root.findtext(f"{info}/{{{NS_SAC}}}SUNATPerceptionDate")
        cashed = self.root.findtext(f"{info}/{{{NS_SAC}}}SUNATTotalCashed")
        self.assertEqual(amt, "23.60")
        self.assertEqual(date_txt, "2026-05-18")
        self.assertEqual(cashed, "1203.60")

    def test_perception_for_imports_uses_regime_03(self):
        self.per.regime_code = "03"
        self.per.regime_percent = Decimal("5")
        root = self.builder.build(self.per)
        self.assertEqual(root.findtext(f"{{{NS_SAC}}}SUNATPerceptionSystemCode"), "03")
        self.assertEqual(root.findtext(f"{{{NS_SAC}}}SUNATPerceptionPercent"), "5")

    def test_serialization_is_well_formed(self):
        xml_bytes = self.builder.build_xml_bytes(self.per)
        parsed = etree.fromstring(xml_bytes)
        self.assertEqual(etree.QName(parsed.tag).localname, "Perception")
