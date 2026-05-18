# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador UBL para Comprobante de Retención SUNAT (catálogo 01, tipo 20).

A diferencia del Invoice UBL 2.1, la Retención usa el esquema SUNAT propio
Retention-1 con namespace 'sac:' para las extensiones:
- Root: <Retention> en urn:sunat:names:specification:ubl:peru:schema:xsd:Retention-1
- Namespace 'sac:' urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1
  para SUNATRetentionDocument, SUNATRetentionInformation, etc.
- UBLVersionID = "2.0" (no 2.1)
- CustomizationID = "1.0"

Estructura mínima:
    <Retention xmlns="...:Retention-1" xmlns:cac="..." xmlns:cbc="..."
               xmlns:ext="..." xmlns:ds="..." xmlns:sac="...">
      <ext:UBLExtensions>...</ext:UBLExtensions>
      <cbc:UBLVersionID>2.0</cbc:UBLVersionID>
      <cbc:CustomizationID>1.0</cbc:CustomizationID>
      <cbc:ID>R001-1</cbc:ID>
      <cbc:IssueDate>2026-05-18</cbc:IssueDate>
      <cac:Signature>...</cac:Signature>
      <cac:AgentParty>...</cac:AgentParty>            <!-- Emisor (Agente Retención) -->
      <cac:ReceiverParty>...</cac:ReceiverParty>      <!-- Sujeto Retenido -->
      <sac:SUNATRetentionSystemCode>01</sac:SUNATRetentionSystemCode>
      <sac:SUNATRetentionPercent>3</sac:SUNATRetentionPercent>
      <cbc:Note>SON TREINTA Y CINCO CON 40/100 SOLES</cbc:Note>
      <cbc:TotalInvoiceAmount currencyID="PEN">35.40</cbc:TotalInvoiceAmount>
      <cbc:TotalPaid currencyID="PEN">1144.60</cbc:TotalPaid>
      <sac:SUNATRetentionDocument>+ ... un bloque por cada documento retenido
    </Retention>
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from lxml import etree

# ─── Namespaces SUNAT Retention-1 ──────────────────────────────────────
NS_RETENTION = "urn:sunat:names:specification:ubl:peru:schema:xsd:Retention-1"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_SAC = "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"

NSMAP_RETENTION = {
    None: NS_RETENTION,
    "cbc": NS_CBC,
    "cac": NS_CAC,
    "ext": NS_EXT,
    "ds": NS_DS,
    "sac": NS_SAC,
}


# Códigos SUNAT catálogo 23 (régimen retención)
RETENTION_REGIME_3PCT = "01"  # Tasa vigente desde 2014


# ─── Dataclasses de entrada ────────────────────────────────────────────


@dataclass
class RetentionParty:
    ruc: str
    doc_type_code: str  # SUNAT cat 06: '6' RUC
    legal_name: str
    address_street: str = ""
    address_country: str = "PE"


@dataclass
class RetentionDocument:
    """Una factura/comprobante que está siendo objeto de retención."""

    doc_type_code: str  # SUNAT cat 01: '01' Factura, '08' ND
    serie_number: str  # "F001-123"
    issue_date: date
    total_amount: Decimal  # Importe total del comprobante (con IGV)
    currency_code: str = "PEN"

    payment_id: str = "1"  # Secuencial del pago (puede ser parcial)
    paid_amount: Decimal = Decimal("0")
    paid_date: date = None  # type: ignore[assignment]

    retention_amount: Decimal = Decimal("0")
    retention_date: date = None  # type: ignore[assignment]
    net_total_cashed: Decimal = Decimal("0")  # = paid - retention

    exchange_rate: Decimal = Decimal("1.000")
    exchange_rate_date: date = None  # type: ignore[assignment]


@dataclass
class Retention:
    serie_number: str  # "R001-1"
    issue_date: date
    note_amount_in_words: str = ""  # "SON TREINTA Y CINCO CON 40/100 SOLES"

    agent: RetentionParty = field(default_factory=lambda: RetentionParty("", "6", ""))
    receiver: RetentionParty = field(default_factory=lambda: RetentionParty("", "6", ""))

    regime_code: str = RETENTION_REGIME_3PCT
    regime_percent: Decimal = Decimal("3")

    total_retention_amount: Decimal = Decimal("0")  # Suma de retenciones líneas
    total_paid: Decimal = Decimal("0")  # Suma de paid_amount líneas
    currency_code: str = "PEN"

    documents: list[RetentionDocument] = field(default_factory=list)


# ─── Builder ───────────────────────────────────────────────────────────


class RetentionUblBuilder:
    """Construye lxml.etree.Element <Retention> desde un objeto Retention.

    Como el Invoice builder, deja un placeholder vacío <ext:ExtensionContent/>
    para que XadesBesSigner lo rellene después.
    """

    def build(self, retention: Retention) -> etree._Element:
        root = etree.Element(f"{{{NS_RETENTION}}}Retention", nsmap=NSMAP_RETENTION)
        self._add_extensions(root)
        self._add_header(root, retention)
        self._add_signature_block(root, retention)
        self._add_agent_party(root, retention.agent)
        self._add_receiver_party(root, retention.receiver)
        self._add_retention_system(root, retention)
        if retention.note_amount_in_words:
            self._cbc(root, "Note", retention.note_amount_in_words, languageLocaleID="1000")
        self._cbc(
            root,
            "TotalInvoiceAmount",
            _fmt(retention.total_retention_amount),
            currencyID=retention.currency_code,
        )
        self._cbc(root, "TotalPaid", _fmt(retention.total_paid), currencyID=retention.currency_code)
        for doc in retention.documents:
            self._add_retention_document(root, doc)
        return root

    def build_xml_bytes(self, retention: Retention) -> bytes:
        root = self.build(retention)
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=False)

    # ─── Subsecciones ────────────────────────────────────────────

    def _add_extensions(self, root):
        exts = etree.SubElement(root, f"{{{NS_EXT}}}UBLExtensions")
        ext = etree.SubElement(exts, f"{{{NS_EXT}}}UBLExtension")
        etree.SubElement(ext, f"{{{NS_EXT}}}ExtensionContent")

    def _add_header(self, root, ret: Retention):
        self._cbc(root, "UBLVersionID", "2.0")
        self._cbc(root, "CustomizationID", "1.0")
        self._cbc(root, "ID", ret.serie_number)
        self._cbc(root, "IssueDate", ret.issue_date.isoformat())

    def _add_signature_block(self, root, ret: Retention):
        sig = etree.SubElement(root, f"{{{NS_CAC}}}Signature")
        self._cbc(sig, "ID", ret.agent.ruc)
        party = etree.SubElement(sig, f"{{{NS_CAC}}}SignatoryParty")
        pid = etree.SubElement(party, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(pid, "ID", ret.agent.ruc)
        pname = etree.SubElement(party, f"{{{NS_CAC}}}PartyName")
        self._cbc(pname, "Name", ret.agent.legal_name)
        dsa = etree.SubElement(sig, f"{{{NS_CAC}}}DigitalSignatureAttachment")
        eref = etree.SubElement(dsa, f"{{{NS_CAC}}}ExternalReference")
        self._cbc(eref, "URI", f"#{ret.agent.ruc}-IDSignatureSP")

    def _add_party(self, parent, party: RetentionParty, role_tag: str):
        wrapper = etree.SubElement(parent, f"{{{NS_CAC}}}{role_tag}")
        party_el = etree.SubElement(wrapper, f"{{{NS_CAC}}}Party")
        identification = etree.SubElement(party_el, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(
            identification,
            "ID",
            party.ruc,
            schemeID=party.doc_type_code,
            schemeAgencyName="PE:SUNAT",
            schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06",
        )
        if party.address_street:
            address = etree.SubElement(party_el, f"{{{NS_CAC}}}PostalAddress")
            country = etree.SubElement(address, f"{{{NS_CAC}}}Country")
            self._cbc(country, "IdentificationCode", party.address_country)
            line = etree.SubElement(address, f"{{{NS_CAC}}}AddressLine")
            self._cbc(line, "Line", party.address_street)
        legal = etree.SubElement(party_el, f"{{{NS_CAC}}}PartyLegalEntity")
        self._cbc(legal, "RegistrationName", party.legal_name)

    def _add_agent_party(self, root, party: RetentionParty):
        self._add_party(root, party, "AgentParty")

    def _add_receiver_party(self, root, party: RetentionParty):
        self._add_party(root, party, "ReceiverParty")

    def _add_retention_system(self, root, ret: Retention):
        etree.SubElement(root, f"{{{NS_SAC}}}SUNATRetentionSystemCode").text = ret.regime_code
        etree.SubElement(root, f"{{{NS_SAC}}}SUNATRetentionPercent").text = _fmt(
            ret.regime_percent, 0
        )

    def _add_retention_document(self, root, doc: RetentionDocument):
        d = etree.SubElement(root, f"{{{NS_SAC}}}SUNATRetentionDocument")
        self._cbc(d, "ID", doc.serie_number, schemeID=doc.doc_type_code)
        self._cbc(d, "IssueDate", doc.issue_date.isoformat())
        self._cbc(d, "TotalInvoiceAmount", _fmt(doc.total_amount), currencyID=doc.currency_code)

        payment = etree.SubElement(d, f"{{{NS_CAC}}}Payment")
        self._cbc(payment, "ID", doc.payment_id)
        self._cbc(payment, "PaidAmount", _fmt(doc.paid_amount), currencyID=doc.currency_code)
        if doc.paid_date:
            self._cbc(payment, "PaidDate", doc.paid_date.isoformat())

        info = etree.SubElement(d, f"{{{NS_SAC}}}SUNATRetentionInformation")
        etree.SubElement(
            info, f"{{{NS_SAC}}}SUNATRetentionAmount", currencyID=doc.currency_code
        ).text = _fmt(doc.retention_amount)
        if doc.retention_date:
            etree.SubElement(
                info, f"{{{NS_SAC}}}SUNATRetentionDate"
            ).text = doc.retention_date.isoformat()
        etree.SubElement(
            info, f"{{{NS_SAC}}}SUNATNetTotalCashed", currencyID=doc.currency_code
        ).text = _fmt(doc.net_total_cashed)
        # ExchangeRate sólo si moneda distinta de PEN o si rate != 1
        if doc.currency_code != "PEN" or doc.exchange_rate != Decimal("1.000"):
            er = etree.SubElement(info, f"{{{NS_CAC}}}ExchangeRate")
            self._cbc(er, "SourceCurrencyCode", doc.currency_code)
            self._cbc(er, "TargetCurrencyCode", "PEN")
            self._cbc(er, "CalculationRate", _fmt(doc.exchange_rate, 3))
            if doc.exchange_rate_date:
                self._cbc(er, "Date", doc.exchange_rate_date.isoformat())

    # ─── Helper ──────────────────────────────────────────────────

    def _cbc(self, parent, tag: str, text: str, **attrs):
        el = etree.SubElement(parent, f"{{{NS_CBC}}}{tag}", **attrs)
        el.text = text
        return el


def _fmt(value, decimals: int = 2) -> str:
    fmt = f"{{:.{decimals}f}}"
    return fmt.format(value if isinstance(value, Decimal) else Decimal(str(value)))
