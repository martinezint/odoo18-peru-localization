# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from lxml import etree
from odoo.tests.common import TransactionCase, tagged

from ..services.retention_ubl_builder import (
    NS_CAC,
    NS_CBC,
    NS_DS,
    NS_EXT,
    NS_RETENTION,
    NS_SAC,
    Retention,
    RetentionDocument,
    RetentionParty,
    RetentionUblBuilder,
)


def _make_minimal_retention():
    ret = Retention(
        serie_number="R001-1",
        issue_date=date(2026, 5, 18),
        note_amount_in_words="SON TREINTA Y CINCO CON 40/100 SOLES",
        agent=RetentionParty(
            ruc="20131312955",
            doc_type_code="6",
            legal_name="EMISOR AGENTE",
        ),
        receiver=RetentionParty(
            ruc="20100047218",
            doc_type_code="6",
            legal_name="SUJETO RETENIDO",
        ),
        regime_code="01",
        regime_percent=Decimal("3"),
    )
    doc = RetentionDocument(
        doc_type_code="01",
        serie_number="F001-123",
        issue_date=date(2026, 5, 15),
        total_amount=Decimal("1180.00"),
        currency_code="PEN",
        payment_id="1",
        paid_amount=Decimal("1180.00"),
        paid_date=date(2026, 5, 18),
        retention_amount=Decimal("35.40"),
        retention_date=date(2026, 5, 18),
        net_total_cashed=Decimal("1144.60"),
    )
    ret.documents.append(doc)
    ret.total_retention_amount = Decimal("35.40")
    ret.total_paid = Decimal("1180.00")
    return ret


@tagged("post_install", "-at_install", "l10n_pe_edi_retention")
class TestRetentionUblBuilder(TransactionCase):
    def setUp(self):
        super().setUp()
        self.builder = RetentionUblBuilder()
        self.ret = _make_minimal_retention()
        self.root = self.builder.build(self.ret)

    # ─── Estructura ───────────────────────────────────────────────

    def test_root_is_retention_in_correct_namespace(self):
        self.assertEqual(etree.QName(self.root.tag).localname, "Retention")
        self.assertEqual(etree.QName(self.root.tag).namespace, NS_RETENTION)

    def test_namespaces_declared_at_root(self):
        nsmap = self.root.nsmap
        self.assertEqual(nsmap.get("cbc"), NS_CBC)
        self.assertEqual(nsmap.get("cac"), NS_CAC)
        self.assertEqual(nsmap.get("ext"), NS_EXT)
        self.assertEqual(nsmap.get("ds"), NS_DS)
        self.assertEqual(nsmap.get("sac"), NS_SAC)

    def test_extension_placeholder_present(self):
        path = f"{{{NS_EXT}}}UBLExtensions/{{{NS_EXT}}}UBLExtension/{{{NS_EXT}}}ExtensionContent"
        ext = self.root.find(path)
        self.assertIsNotNone(ext)
        self.assertEqual(len(list(ext)), 0)

    def test_header_fields(self):
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}UBLVersionID"), "2.0")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}CustomizationID"), "1.0")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}ID"), "R001-1")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}IssueDate"), "2026-05-18")

    # ─── Agente / Receiver ────────────────────────────────────────

    def test_agent_party_ruc_and_name(self):
        ruc = self.root.findtext(
            f"{{{NS_CAC}}}AgentParty/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyIdentification/{{{NS_CBC}}}ID"
        )
        name = self.root.findtext(
            f"{{{NS_CAC}}}AgentParty/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyLegalEntity/{{{NS_CBC}}}RegistrationName"
        )
        self.assertEqual(ruc, "20131312955")
        self.assertEqual(name, "EMISOR AGENTE")

    def test_receiver_party_ruc(self):
        ruc = self.root.findtext(
            f"{{{NS_CAC}}}ReceiverParty/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyIdentification/{{{NS_CBC}}}ID"
        )
        self.assertEqual(ruc, "20100047218")

    # ─── SUNAT regime ─────────────────────────────────────────────

    def test_sunat_retention_system_and_percent(self):
        self.assertEqual(self.root.findtext(f"{{{NS_SAC}}}SUNATRetentionSystemCode"), "01")
        self.assertEqual(self.root.findtext(f"{{{NS_SAC}}}SUNATRetentionPercent"), "3")

    def test_total_invoice_amount_is_total_retention(self):
        amt = self.root.find(f"{{{NS_CBC}}}TotalInvoiceAmount")
        self.assertEqual(amt.text, "35.40")
        self.assertEqual(amt.get("currencyID"), "PEN")

    def test_total_paid(self):
        amt = self.root.find(f"{{{NS_CBC}}}TotalPaid")
        self.assertEqual(amt.text, "1180.00")

    def test_note_with_locale(self):
        note = self.root.find(f"{{{NS_CBC}}}Note")
        self.assertEqual(note.text, "SON TREINTA Y CINCO CON 40/100 SOLES")
        self.assertEqual(note.get("languageLocaleID"), "1000")

    # ─── Retention document ───────────────────────────────────────

    def test_one_retention_document(self):
        docs = self.root.findall(f"{{{NS_SAC}}}SUNATRetentionDocument")
        self.assertEqual(len(docs), 1)

    def test_document_serie_number_with_scheme_id(self):
        doc_id = self.root.find(f"{{{NS_SAC}}}SUNATRetentionDocument/{{{NS_CBC}}}ID")
        self.assertEqual(doc_id.text, "F001-123")
        self.assertEqual(doc_id.get("schemeID"), "01")  # Factura

    def test_document_total_invoice_amount(self):
        amt = self.root.findtext(
            f"{{{NS_SAC}}}SUNATRetentionDocument/{{{NS_CBC}}}TotalInvoiceAmount"
        )
        self.assertEqual(amt, "1180.00")

    def test_document_payment(self):
        paid = self.root.findtext(
            f"{{{NS_SAC}}}SUNATRetentionDocument/{{{NS_CAC}}}Payment/{{{NS_CBC}}}PaidAmount"
        )
        paid_date = self.root.findtext(
            f"{{{NS_SAC}}}SUNATRetentionDocument/{{{NS_CAC}}}Payment/{{{NS_CBC}}}PaidDate"
        )
        self.assertEqual(paid, "1180.00")
        self.assertEqual(paid_date, "2026-05-18")

    def test_document_retention_info(self):
        info_path = f"{{{NS_SAC}}}SUNATRetentionDocument/{{{NS_SAC}}}SUNATRetentionInformation"
        ret_amt = self.root.findtext(f"{info_path}/{{{NS_SAC}}}SUNATRetentionAmount")
        ret_date = self.root.findtext(f"{info_path}/{{{NS_SAC}}}SUNATRetentionDate")
        net = self.root.findtext(f"{info_path}/{{{NS_SAC}}}SUNATNetTotalCashed")
        self.assertEqual(ret_amt, "35.40")
        self.assertEqual(ret_date, "2026-05-18")
        self.assertEqual(net, "1144.60")

    def test_exchange_rate_omitted_for_pen_with_rate_1(self):
        """No debe haber ExchangeRate cuando la moneda es PEN y rate=1."""
        er = self.root.find(
            f"{{{NS_SAC}}}SUNATRetentionDocument"
            f"/{{{NS_SAC}}}SUNATRetentionInformation"
            f"/{{{NS_CAC}}}ExchangeRate"
        )
        self.assertIsNone(er, "ExchangeRate no debe aparecer para PEN con rate 1")

    # ─── Serialization ────────────────────────────────────────────

    def test_serialization_is_well_formed(self):
        xml_bytes = self.builder.build_xml_bytes(self.ret)
        self.assertTrue(xml_bytes.startswith(b"<?xml"))
        parsed = etree.fromstring(xml_bytes)
        self.assertEqual(etree.QName(parsed.tag).localname, "Retention")


@tagged("post_install", "-at_install", "l10n_pe_edi_retention")
class TestRetentionUblExchangeRate(TransactionCase):
    """Exchange rate aparece sólo si moneda != PEN o rate != 1."""

    def setUp(self):
        super().setUp()
        self.builder = RetentionUblBuilder()

    def test_exchange_rate_for_usd_document(self):
        ret = _make_minimal_retention()
        ret.documents[0].currency_code = "USD"
        ret.documents[0].exchange_rate = Decimal("3.752")
        ret.documents[0].exchange_rate_date = date(2026, 5, 18)
        root = self.builder.build(ret)
        er = root.find(
            f"{{{NS_SAC}}}SUNATRetentionDocument"
            f"/{{{NS_SAC}}}SUNATRetentionInformation"
            f"/{{{NS_CAC}}}ExchangeRate"
        )
        self.assertIsNotNone(er, "ExchangeRate debe aparecer cuando moneda=USD")
        rate = er.findtext(f"{{{NS_CBC}}}CalculationRate")
        self.assertEqual(rate, "3.752")
