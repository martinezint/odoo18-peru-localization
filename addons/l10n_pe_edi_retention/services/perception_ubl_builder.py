# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador UBL para Comprobante de Percepción SUNAT (catálogo 01, tipo 40).

Estructura espejo de Retention pero:
- Root: <Perception> en NS_PERCEPTION (Perception-1)
- AgentParty = Agente de Percepción (emisor); ReceiverParty = Cliente percibido
- SUNATPerceptionSystemCode (cat 22): 01 venta interna, 02 combustible,
  03 importación
- SUNATPerceptionPercent: 2 (1, 0.5 según régimen)
- SUNATPerceptionDocument > SUNATPerceptionInformation con
  SUNATPerceptionAmount, SUNATPerceptionDate, SUNATTotalCashed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from lxml import etree

NS_PERCEPTION = "urn:sunat:names:specification:ubl:peru:schema:xsd:Perception-1"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_SAC = "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"

NSMAP_PERCEPTION = {
    None: NS_PERCEPTION,
    "cbc": NS_CBC,
    "cac": NS_CAC,
    "ext": NS_EXT,
    "ds": NS_DS,
    "sac": NS_SAC,
}


# Códigos SUNAT catálogo 22 (régimen percepción)
PERCEPTION_REGIME_INTERNAL_SALE = "01"  # Venta interna — 2%
PERCEPTION_REGIME_FUEL = "02"  # Combustible — 1%
PERCEPTION_REGIME_IMPORT = "03"  # Importación — 5%


@dataclass
class PerceptionParty:
    ruc: str
    doc_type_code: str  # SUNAT cat 06: '6' RUC
    legal_name: str
    address_street: str = ""
    address_country: str = "PE"


@dataclass
class PerceptionDocument:
    """Una factura sobre la cual el agente está percibiendo IGV."""

    doc_type_code: str
    serie_number: str
    issue_date: date
    total_amount: Decimal
    currency_code: str = "PEN"

    payment_id: str = "1"
    paid_amount: Decimal = Decimal("0")
    paid_date: date = None  # type: ignore[assignment]

    perception_amount: Decimal = Decimal("0")
    perception_date: date = None  # type: ignore[assignment]
    total_cashed: Decimal = Decimal("0")  # = paid + perception

    exchange_rate: Decimal = Decimal("1.000")
    exchange_rate_date: date = None  # type: ignore[assignment]


@dataclass
class Perception:
    serie_number: str
    issue_date: date
    note_amount_in_words: str = ""

    agent: PerceptionParty = field(default_factory=lambda: PerceptionParty("", "6", ""))
    receiver: PerceptionParty = field(default_factory=lambda: PerceptionParty("", "6", ""))

    regime_code: str = PERCEPTION_REGIME_INTERNAL_SALE
    regime_percent: Decimal = Decimal("2")

    total_perception_amount: Decimal = Decimal("0")
    total_cashed: Decimal = Decimal("0")
    currency_code: str = "PEN"

    documents: list[PerceptionDocument] = field(default_factory=list)


class PerceptionUblBuilder:
    """Construye <Perception> UBL desde un objeto Perception."""

    def build(self, perception: Perception) -> etree._Element:
        root = etree.Element(f"{{{NS_PERCEPTION}}}Perception", nsmap=NSMAP_PERCEPTION)
        self._add_extensions(root)
        self._add_header(root, perception)
        self._add_signature_block(root, perception)
        self._add_agent_party(root, perception.agent)
        self._add_receiver_party(root, perception.receiver)
        self._add_perception_system(root, perception)
        if perception.note_amount_in_words:
            self._cbc(root, "Note", perception.note_amount_in_words, languageLocaleID="1000")
        self._cbc(
            root,
            "TotalInvoiceAmount",
            _fmt(perception.total_perception_amount),
            currencyID=perception.currency_code,
        )
        self._cbc(
            root, "TotalPaid", _fmt(perception.total_cashed), currencyID=perception.currency_code
        )
        for doc in perception.documents:
            self._add_perception_document(root, doc)
        return root

    def build_xml_bytes(self, perception: Perception) -> bytes:
        root = self.build(perception)
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=False)

    def _add_extensions(self, root):
        exts = etree.SubElement(root, f"{{{NS_EXT}}}UBLExtensions")
        ext = etree.SubElement(exts, f"{{{NS_EXT}}}UBLExtension")
        etree.SubElement(ext, f"{{{NS_EXT}}}ExtensionContent")

    def _add_header(self, root, per: Perception):
        self._cbc(root, "UBLVersionID", "2.0")
        self._cbc(root, "CustomizationID", "1.0")
        self._cbc(root, "ID", per.serie_number)
        self._cbc(root, "IssueDate", per.issue_date.isoformat())

    def _add_signature_block(self, root, per: Perception):
        sig = etree.SubElement(root, f"{{{NS_CAC}}}Signature")
        self._cbc(sig, "ID", per.agent.ruc)
        party = etree.SubElement(sig, f"{{{NS_CAC}}}SignatoryParty")
        pid = etree.SubElement(party, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(pid, "ID", per.agent.ruc)
        pname = etree.SubElement(party, f"{{{NS_CAC}}}PartyName")
        self._cbc(pname, "Name", per.agent.legal_name)
        dsa = etree.SubElement(sig, f"{{{NS_CAC}}}DigitalSignatureAttachment")
        eref = etree.SubElement(dsa, f"{{{NS_CAC}}}ExternalReference")
        self._cbc(eref, "URI", f"#{per.agent.ruc}-IDSignatureSP")

    def _add_party(self, parent, party: PerceptionParty, role_tag: str):
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

    def _add_agent_party(self, root, party):
        self._add_party(root, party, "AgentParty")

    def _add_receiver_party(self, root, party):
        self._add_party(root, party, "ReceiverParty")

    def _add_perception_system(self, root, per: Perception):
        etree.SubElement(root, f"{{{NS_SAC}}}SUNATPerceptionSystemCode").text = per.regime_code
        etree.SubElement(root, f"{{{NS_SAC}}}SUNATPerceptionPercent").text = _fmt(
            per.regime_percent, 0
        )

    def _add_perception_document(self, root, doc: PerceptionDocument):
        d = etree.SubElement(root, f"{{{NS_SAC}}}SUNATPerceptionDocumentReference")
        self._cbc(d, "ID", doc.serie_number, schemeID=doc.doc_type_code)
        self._cbc(d, "IssueDate", doc.issue_date.isoformat())
        self._cbc(d, "TotalInvoiceAmount", _fmt(doc.total_amount), currencyID=doc.currency_code)

        payment = etree.SubElement(d, f"{{{NS_CAC}}}Payment")
        self._cbc(payment, "ID", doc.payment_id)
        self._cbc(payment, "PaidAmount", _fmt(doc.paid_amount), currencyID=doc.currency_code)
        if doc.paid_date:
            self._cbc(payment, "PaidDate", doc.paid_date.isoformat())

        info = etree.SubElement(d, f"{{{NS_SAC}}}SUNATPerceptionInformation")
        etree.SubElement(
            info, f"{{{NS_SAC}}}SUNATPerceptionAmount", currencyID=doc.currency_code
        ).text = _fmt(doc.perception_amount)
        if doc.perception_date:
            etree.SubElement(
                info, f"{{{NS_SAC}}}SUNATPerceptionDate"
            ).text = doc.perception_date.isoformat()
        etree.SubElement(
            info, f"{{{NS_SAC}}}SUNATTotalCashed", currencyID=doc.currency_code
        ).text = _fmt(doc.total_cashed)
        if doc.currency_code != "PEN" or doc.exchange_rate != Decimal("1.000"):
            er = etree.SubElement(info, f"{{{NS_CAC}}}ExchangeRate")
            self._cbc(er, "SourceCurrencyCode", doc.currency_code)
            self._cbc(er, "TargetCurrencyCode", "PEN")
            self._cbc(er, "CalculationRate", _fmt(doc.exchange_rate, 3))
            if doc.exchange_rate_date:
                self._cbc(er, "Date", doc.exchange_rate_date.isoformat())

    def _cbc(self, parent, tag: str, text: str, **attrs):
        el = etree.SubElement(parent, f"{{{NS_CBC}}}{tag}", **attrs)
        el.text = text
        return el


def _fmt(value, decimals: int = 2) -> str:
    fmt = f"{{:.{decimals}f}}"
    return fmt.format(value if isinstance(value, Decimal) else Decimal(str(value)))
