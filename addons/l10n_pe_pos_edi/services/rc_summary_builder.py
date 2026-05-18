# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador UBL para Resumen Diario de Boletas (SUNAT cat 01, tipo RC).

Estructura: <SummaryDocuments> en el esquema SUNAT SummaryDocuments-1.

  <SummaryDocuments xmlns="...:SummaryDocuments-1"
                    xmlns:cbc="..." xmlns:cac="..." xmlns:ext="..."
                    xmlns:sac="..." xmlns:ds="...">
    <ext:UBLExtensions>...</ext:UBLExtensions>
    <cbc:UBLVersionID>2.0</cbc:UBLVersionID>
    <cbc:CustomizationID>1.1</cbc:CustomizationID>
    <cbc:ID>RC-20260518-001</cbc:ID>
    <cbc:ReferenceDate>2026-05-17</cbc:ReferenceDate>     <!-- fecha de las boletas -->
    <cbc:IssueDate>2026-05-18</cbc:IssueDate>             <!-- fecha del resumen (D+1 OK) -->
    <cac:Signature>...</cac:Signature>
    <cac:AccountingSupplierParty>...</cac:AccountingSupplierParty>
    <sac:SummaryDocumentsLine>+
      <cbc:LineID>1</cbc:LineID>
      <cbc:DocumentTypeCode>03</cbc:DocumentTypeCode>
      <sac:DocumentSerialID>B001</sac:DocumentSerialID>
      <sac:StartDocumentNumberID>1</sac:StartDocumentNumberID>
      <sac:EndDocumentNumberID>1</sac:EndDocumentNumberID>
      <sac:TotalAmount currencyID="PEN">118.00</sac:TotalAmount>
      <sac:BillingPayments>
        <cbc:PaidAmount currencyID="PEN">100.00</cbc:PaidAmount>
        <cbc:InstructionID>01</cbc:InstructionID>     <!-- 01 gravado -->
      </sac:BillingPayments>
      <cac:TaxTotal>
        <cbc:TaxAmount currencyID="PEN">18.00</cbc:TaxAmount>
        <cac:TaxSubtotal>
          <cbc:TaxAmount currencyID="PEN">18.00</cbc:TaxAmount>
          <cac:TaxCategory>
            <cac:TaxScheme><cbc:ID>1000</cbc:ID><cbc:Name>IGV</cbc:Name><cbc:TaxTypeCode>VAT</cbc:TaxTypeCode></cac:TaxScheme>
          </cac:TaxCategory>
        </cac:TaxSubtotal>
      </cac:TaxTotal>
    </sac:SummaryDocumentsLine>
    ...
  </SummaryDocuments>

v1: una <SummaryDocumentsLine> por cada boleta individual (start=end=número).
v2 podría colapsar rangos consecutivos para reducir tamaño del XML.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from lxml import etree


NS_SUMMARY = "urn:sunat:names:specification:ubl:peru:schema:xsd:SummaryDocuments-1"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_SAC = "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"

NSMAP_SUMMARY = {
    None: NS_SUMMARY,
    "cbc": NS_CBC,
    "cac": NS_CAC,
    "ext": NS_EXT,
    "ds": NS_DS,
    "sac": NS_SAC,
}


@dataclass
class RcSupplier:
    ruc: str
    legal_name: str


@dataclass
class RcLine:
    """Una boleta dentro del resumen."""
    line_id: int                       # 1, 2, 3...
    document_type_code: str = "03"     # cat 1: 03 Boleta, 07 NC sobre boleta
    serie: str = ""                    # ej. 'B001'
    start_number: str = "0"            # número desde (string para preservar leading zeros)
    end_number: str = "0"              # número hasta
    total_amount: Decimal = Decimal("0.00")
    payable_amount: Decimal = Decimal("0.00")  # base imponible operación gravada (cbc:PaidAmount con InstructionID=01)
    tax_amount: Decimal = Decimal("0.00")       # IGV total de la(s) boleta(s) en el rango
    currency: str = "PEN"


@dataclass
class RcSummary:
    serie_number: str                  # 'RC-20260518-001'
    reference_date: date               # fecha de las boletas (día anterior típico)
    issue_date: date                   # fecha de emisión del resumen
    supplier: RcSupplier = field(default_factory=lambda: RcSupplier("", ""))
    lines: list[RcLine] = field(default_factory=list)


class RcSummaryBuilder:
    """Construye <SummaryDocuments> SUNAT desde un RcSummary."""

    def build(self, summary: RcSummary) -> etree._Element:
        root = etree.Element(f"{{{NS_SUMMARY}}}SummaryDocuments", nsmap=NSMAP_SUMMARY)
        self._add_extensions(root)
        self._add_header(root, summary)
        self._add_signature_block(root, summary)
        self._add_supplier(root, summary.supplier)
        for line in summary.lines:
            self._add_line(root, line)
        return root

    def build_xml_bytes(self, summary: RcSummary) -> bytes:
        return etree.tostring(
            self.build(summary),
            xml_declaration=True,
            encoding="UTF-8",
            standalone=False,
        )

    def _add_extensions(self, root):
        exts = etree.SubElement(root, f"{{{NS_EXT}}}UBLExtensions")
        ext = etree.SubElement(exts, f"{{{NS_EXT}}}UBLExtension")
        etree.SubElement(ext, f"{{{NS_EXT}}}ExtensionContent")

    def _add_header(self, root, s: RcSummary):
        self._cbc(root, "UBLVersionID", "2.0")
        self._cbc(root, "CustomizationID", "1.1")
        self._cbc(root, "ID", s.serie_number)
        self._cbc(root, "ReferenceDate", s.reference_date.isoformat())
        self._cbc(root, "IssueDate", s.issue_date.isoformat())

    def _add_signature_block(self, root, s: RcSummary):
        sig = etree.SubElement(root, f"{{{NS_CAC}}}Signature")
        self._cbc(sig, "ID", s.supplier.ruc)
        sp = etree.SubElement(sig, f"{{{NS_CAC}}}SignatoryParty")
        pid = etree.SubElement(sp, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(pid, "ID", s.supplier.ruc)
        pname = etree.SubElement(sp, f"{{{NS_CAC}}}PartyName")
        self._cbc(pname, "Name", s.supplier.legal_name)
        dsa = etree.SubElement(sig, f"{{{NS_CAC}}}DigitalSignatureAttachment")
        eref = etree.SubElement(dsa, f"{{{NS_CAC}}}ExternalReference")
        self._cbc(eref, "URI", f"#{s.supplier.ruc}-IDSignatureSP")

    def _add_supplier(self, root, sup: RcSupplier):
        wrapper = etree.SubElement(root, f"{{{NS_CAC}}}AccountingSupplierParty")
        self._cbc(wrapper, "CustomerAssignedAccountID", sup.ruc)
        # AdditionalAccountID = 6 (RUC)
        etree.SubElement(wrapper, f"{{{NS_CBC}}}AdditionalAccountID").text = "6"
        party = etree.SubElement(wrapper, f"{{{NS_CAC}}}Party")
        legal = etree.SubElement(party, f"{{{NS_CAC}}}PartyLegalEntity")
        self._cbc(legal, "RegistrationName", sup.legal_name)

    def _add_line(self, root, line: RcLine):
        ln = etree.SubElement(root, f"{{{NS_SAC}}}SummaryDocumentsLine")
        self._cbc(ln, "LineID", str(line.line_id))
        self._cbc(ln, "DocumentTypeCode", line.document_type_code)
        etree.SubElement(ln, f"{{{NS_SAC}}}DocumentSerialID").text = line.serie
        etree.SubElement(ln, f"{{{NS_SAC}}}StartDocumentNumberID").text = line.start_number
        etree.SubElement(ln, f"{{{NS_SAC}}}EndDocumentNumberID").text = line.end_number
        etree.SubElement(ln, f"{{{NS_SAC}}}TotalAmount",
                         currencyID=line.currency).text = _fmt(line.total_amount)
        # BillingPayments: operación gravada (01)
        bp = etree.SubElement(ln, f"{{{NS_SAC}}}BillingPayments")
        self._cbc(bp, "PaidAmount", _fmt(line.payable_amount), currencyID=line.currency)
        self._cbc(bp, "InstructionID", "01")
        # TaxTotal IGV
        tt = etree.SubElement(ln, f"{{{NS_CAC}}}TaxTotal")
        self._cbc(tt, "TaxAmount", _fmt(line.tax_amount), currencyID=line.currency)
        sub = etree.SubElement(tt, f"{{{NS_CAC}}}TaxSubtotal")
        self._cbc(sub, "TaxAmount", _fmt(line.tax_amount), currencyID=line.currency)
        cat = etree.SubElement(sub, f"{{{NS_CAC}}}TaxCategory")
        scheme = etree.SubElement(cat, f"{{{NS_CAC}}}TaxScheme")
        self._cbc(scheme, "ID", "1000")
        self._cbc(scheme, "Name", "IGV")
        self._cbc(scheme, "TaxTypeCode", "VAT")

    def _cbc(self, parent, tag: str, text: str, **attrs):
        el = etree.SubElement(parent, f"{{{NS_CBC}}}{tag}", **attrs)
        el.text = text
        return el


def _fmt(value, decimals: int = 2) -> str:
    if value is None:
        return f"{Decimal('0'):.{decimals}f}"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.{decimals}f}"
