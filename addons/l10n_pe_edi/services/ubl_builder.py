# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador de XML UBL 2.1 para Factura electrónica SUNAT (catálogo 01, tipo 01).

Este módulo construye el XML SIN firma. La firma se aplica después con
`xades_signer.py` sobre el `<ext:ExtensionContent>` placeholder.

Spec base: Manual del Programador FE SUNAT v2.1 + UBL 2.1 OASIS.
Customization SUNAT: CustomizationID = "2.0".

Estructura mínima de una Factura UBL 2.1 que SUNAT acepta:

    <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" ...>
      <ext:UBLExtensions>
        <ext:UBLExtension>
          <ext:ExtensionContent/>  <!-- placeholder firma -->
        </ext:UBLExtension>
      </ext:UBLExtensions>
      <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
      <cbc:CustomizationID>2.0</cbc:CustomizationID>
      <cbc:ID>F001-1</cbc:ID>
      <cbc:IssueDate>2026-05-15</cbc:IssueDate>
      <cbc:IssueTime>10:30:00</cbc:IssueTime>
      <cbc:DueDate>2026-06-15</cbc:DueDate>
      <cbc:InvoiceTypeCode listID="0101">01</cbc:InvoiceTypeCode>
      <cbc:Note languageLocaleID="1000">SON CIEN CON 00/100 SOLES</cbc:Note>
      <cbc:DocumentCurrencyCode>PEN</cbc:DocumentCurrencyCode>
      <cac:Signature> ... metadata firma ... </cac:Signature>
      <cac:AccountingSupplierParty> ... emisor con RUC ... </cac:AccountingSupplierParty>
      <cac:AccountingCustomerParty> ... cliente con RUC/DNI ... </cac:AccountingCustomerParty>
      <cac:TaxTotal> ... IGV ... </cac:TaxTotal>
      <cac:LegalMonetaryTotal> ... totales ... </cac:LegalMonetaryTotal>
      <cac:InvoiceLine>+ ... líneas ... </cac:InvoiceLine>
    </Invoice>
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal
from typing import Optional

from lxml import etree


# ─── Namespaces SUNAT/UBL 2.1 ──────────────────────────────────────────
NS_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

NSMAP = {
    None: NS_INVOICE,
    "cbc": NS_CBC,
    "cac": NS_CAC,
    "ext": NS_EXT,
    "ds": NS_DS,
    "xsi": NS_XSI,
}


# ─── Data classes (input al builder) ───────────────────────────────────

@dataclass
class Party:
    """Emisor o cliente. Cumple con cac:AccountingSupplierParty / CustomerParty."""
    ruc: str                       # RUC o DNI
    doc_type_code: str             # SUNAT catálogo 06: '6' RUC, '1' DNI, '4' CE
    legal_name: str                # Razón social
    commercial_name: str = ""
    address_street: str = ""
    address_district: str = ""     # Ej. "MIRAFLORES"
    address_city: str = ""         # Ej. "LIMA"
    address_country: str = "PE"
    ubigeo: str = ""               # Ej. "150122" (Miraflores)


@dataclass
class InvoiceLine:
    line_id: int                   # Secuencial 1, 2, 3...
    description: str
    quantity: Decimal
    unit_code: str = "NIU"         # Unidad SUNAT
    unit_price: Decimal = Decimal("0")
    line_extension_amount: Decimal = Decimal("0")  # cantidad × precio sin IGV
    igv_amount: Decimal = Decimal("0")             # IGV de la línea
    igv_affectation_code: str = "10"               # Cat 07: 10=Gravado, 20=Exo, 30=Inafecto
    igv_percentage: Decimal = Decimal("18")        # Tasa IGV aplicada (18% típico)


@dataclass
class Invoice:
    """Factura SUNAT 01 — versión mínima para v1."""
    serie_number: str              # "F001-1"
    issue_date: date
    issue_time: time
    due_date: Optional[date] = None
    operation_type_code: str = "0101"  # Cat 51: 0101 Venta interna
    currency_code: str = "PEN"
    note_amount_in_words: str = ""     # "SON CIEN CON 00/100 SOLES"

    supplier: Party = field(default_factory=lambda: Party("", "6", ""))
    customer: Party = field(default_factory=lambda: Party("", "6", ""))

    lines: list[InvoiceLine] = field(default_factory=list)

    # Totales (deben ser consistentes con líneas — el builder no recalcula)
    total_igv: Decimal = Decimal("0")
    total_taxed: Decimal = Decimal("0")          # Base imponible operaciones gravadas
    total_line_extension: Decimal = Decimal("0")  # Suma de cbc:LineExtensionAmount
    total_payable: Decimal = Decimal("0")         # Importe total a pagar
    total_tax_exclusive: Decimal = Decimal("0")   # Subtotal sin IGV
    total_tax_inclusive: Decimal = Decimal("0")   # Subtotal con IGV (típicamente == payable)


# ─── Builder ────────────────────────────────────────────────────────────

class UblInvoiceBuilder:
    """Construye lxml.etree.Element <Invoice> desde un objeto Invoice.

    El XML resultante tiene un placeholder `<ext:ExtensionContent/>` vacío
    donde la firma XAdES-BES se inserta después (xades_signer.py).
    """

    def build(self, invoice: Invoice) -> etree._Element:
        root = etree.Element(f"{{{NS_INVOICE}}}Invoice", nsmap=NSMAP)

        self._add_extensions(root)
        self._add_header(root, invoice)
        self._add_signature_block(root, invoice)
        self._add_supplier(root, invoice.supplier)
        self._add_customer(root, invoice.customer)
        self._add_tax_total(root, invoice)
        self._add_monetary_totals(root, invoice)
        self._add_lines(root, invoice.lines, invoice.currency_code)

        return root

    def build_xml_bytes(self, invoice: Invoice) -> bytes:
        """Helper: build + serialize a bytes UTF-8 con declaración XML."""
        root = self.build(invoice)
        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=False
        )

    # ─── Subsecciones ─────────────────────────────────────────────────

    def _add_extensions(self, root):
        """ext:UBLExtensions con un ext:UBLExtension/ExtensionContent vacío
        que sirve de placeholder para la firma XAdES."""
        exts = etree.SubElement(root, f"{{{NS_EXT}}}UBLExtensions")
        ext = etree.SubElement(exts, f"{{{NS_EXT}}}UBLExtension")
        etree.SubElement(ext, f"{{{NS_EXT}}}ExtensionContent")

    def _add_header(self, root, inv: Invoice):
        self._cbc(root, "UBLVersionID", "2.1")
        self._cbc(root, "CustomizationID", "2.0")
        self._cbc(root, "ID", inv.serie_number)
        self._cbc(root, "IssueDate", inv.issue_date.isoformat())
        self._cbc(root, "IssueTime", inv.issue_time.isoformat())
        if inv.due_date:
            self._cbc(root, "DueDate", inv.due_date.isoformat())
        self._cbc(root, "InvoiceTypeCode", "01", listID=inv.operation_type_code)
        if inv.note_amount_in_words:
            self._cbc(root, "Note", inv.note_amount_in_words, languageLocaleID="1000")
        self._cbc(root, "DocumentCurrencyCode", inv.currency_code)

    def _add_signature_block(self, root, inv: Invoice):
        """cac:Signature: metadata de la firma (separada del <ds:Signature> en sí).

        SUNAT lo requiere aunque la firma real va en ext:UBLExtensions.
        """
        sig = etree.SubElement(root, f"{{{NS_CAC}}}Signature")
        self._cbc(sig, "ID", "IDSignatureSP")
        signatory = etree.SubElement(sig, f"{{{NS_CAC}}}SignatoryParty")
        party_id = etree.SubElement(signatory, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(party_id, "ID", inv.supplier.ruc)
        party_name = etree.SubElement(signatory, f"{{{NS_CAC}}}PartyName")
        self._cbc(party_name, "Name", inv.supplier.legal_name)
        digital = etree.SubElement(sig, f"{{{NS_CAC}}}DigitalSignatureAttachment")
        ext_ref = etree.SubElement(digital, f"{{{NS_CAC}}}ExternalReference")
        self._cbc(ext_ref, "URI", f"#{inv.supplier.ruc}-IDSignatureSP")

    def _add_party(self, parent, party: Party, role_tag: str):
        """Bloque común para supplier/customer."""
        wrapper = etree.SubElement(parent, f"{{{NS_CAC}}}{role_tag}")
        party_el = etree.SubElement(wrapper, f"{{{NS_CAC}}}Party")

        # PartyIdentification (doc identidad)
        identification = etree.SubElement(party_el, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(identification, "ID", party.ruc, schemeID=party.doc_type_code,
                  schemeName="Documento de Identidad",
                  schemeAgencyName="PE:SUNAT",
                  schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06")

        # PartyName (nombre comercial — opcional)
        if party.commercial_name:
            party_name = etree.SubElement(party_el, f"{{{NS_CAC}}}PartyName")
            self._cbc(party_name, "Name", party.commercial_name)

        # PostalAddress
        if party.address_street or party.ubigeo:
            address = etree.SubElement(party_el, f"{{{NS_CAC}}}PostalAddress")
            if party.ubigeo:
                self._cbc(address, "ID", party.ubigeo)
            if party.address_district:
                self._cbc(address, "District", party.address_district)
            if party.address_city:
                self._cbc(address, "CityName", party.address_city)
            country = etree.SubElement(address, f"{{{NS_CAC}}}Country")
            self._cbc(country, "IdentificationCode", party.address_country)
            if party.address_street:
                line = etree.SubElement(address, f"{{{NS_CAC}}}AddressLine")
                self._cbc(line, "Line", party.address_street)

        # PartyLegalEntity (razón social)
        legal = etree.SubElement(party_el, f"{{{NS_CAC}}}PartyLegalEntity")
        self._cbc(legal, "RegistrationName", party.legal_name)

    def _add_supplier(self, root, party: Party):
        self._add_party(root, party, "AccountingSupplierParty")

    def _add_customer(self, root, party: Party):
        self._add_party(root, party, "AccountingCustomerParty")

    def _add_tax_total(self, root, inv: Invoice):
        tax_total = etree.SubElement(root, f"{{{NS_CAC}}}TaxTotal")
        self._cbc(tax_total, "TaxAmount", _fmt(inv.total_igv), currencyID=inv.currency_code)
        # TaxSubtotal IGV
        subtotal = etree.SubElement(tax_total, f"{{{NS_CAC}}}TaxSubtotal")
        self._cbc(subtotal, "TaxableAmount", _fmt(inv.total_taxed), currencyID=inv.currency_code)
        self._cbc(subtotal, "TaxAmount", _fmt(inv.total_igv), currencyID=inv.currency_code)
        category = etree.SubElement(subtotal, f"{{{NS_CAC}}}TaxCategory")
        tax_scheme = etree.SubElement(category, f"{{{NS_CAC}}}TaxScheme")
        self._cbc(tax_scheme, "ID", "1000")  # IGV
        self._cbc(tax_scheme, "Name", "IGV")
        self._cbc(tax_scheme, "TaxTypeCode", "VAT")

    def _add_monetary_totals(self, root, inv: Invoice):
        m = etree.SubElement(root, f"{{{NS_CAC}}}LegalMonetaryTotal")
        self._cbc(m, "LineExtensionAmount", _fmt(inv.total_line_extension), currencyID=inv.currency_code)
        self._cbc(m, "TaxInclusiveAmount", _fmt(inv.total_tax_inclusive), currencyID=inv.currency_code)
        self._cbc(m, "TaxExclusiveAmount", _fmt(inv.total_tax_exclusive), currencyID=inv.currency_code)
        self._cbc(m, "PayableAmount", _fmt(inv.total_payable), currencyID=inv.currency_code)

    def _add_lines(self, root, lines: list[InvoiceLine], currency: str):
        for line in lines:
            self._add_line(root, line, currency)

    def _add_line(self, root, line: InvoiceLine, currency: str):
        l = etree.SubElement(root, f"{{{NS_CAC}}}InvoiceLine")
        self._cbc(l, "ID", str(line.line_id))
        self._cbc(l, "InvoicedQuantity", _fmt(line.quantity, 3), unitCode=line.unit_code)
        self._cbc(l, "LineExtensionAmount", _fmt(line.line_extension_amount), currencyID=currency)

        # Tax info por línea
        tax_total = etree.SubElement(l, f"{{{NS_CAC}}}TaxTotal")
        self._cbc(tax_total, "TaxAmount", _fmt(line.igv_amount), currencyID=currency)
        subtotal = etree.SubElement(tax_total, f"{{{NS_CAC}}}TaxSubtotal")
        self._cbc(subtotal, "TaxableAmount", _fmt(line.line_extension_amount), currencyID=currency)
        self._cbc(subtotal, "TaxAmount", _fmt(line.igv_amount), currencyID=currency)
        category = etree.SubElement(subtotal, f"{{{NS_CAC}}}TaxCategory")
        self._cbc(category, "Percent", _fmt(line.igv_percentage, 2))
        self._cbc(category, "TaxExemptionReasonCode", line.igv_affectation_code,
                  listAgencyName="PE:SUNAT",
                  listName="SUNAT:Codigo de Tipo de Afectacion del IGV",
                  listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07")
        scheme = etree.SubElement(category, f"{{{NS_CAC}}}TaxScheme")
        self._cbc(scheme, "ID", "1000")
        self._cbc(scheme, "Name", "IGV")
        self._cbc(scheme, "TaxTypeCode", "VAT")

        # Item
        item = etree.SubElement(l, f"{{{NS_CAC}}}Item")
        self._cbc(item, "Description", line.description)

        # Price
        price = etree.SubElement(l, f"{{{NS_CAC}}}Price")
        self._cbc(price, "PriceAmount", _fmt(line.unit_price), currencyID=currency)

    # ─── Helper ─────────────────────────────────────────────────────

    def _cbc(self, parent, tag: str, text: str, **attrs) -> etree._Element:
        el = etree.SubElement(parent, f"{{{NS_CBC}}}{tag}", **attrs)
        el.text = text
        return el


def _fmt(value: Decimal, decimals: int = 2) -> str:
    """Formatea Decimal a string con N decimales (SUNAT exige 2 normalmente,
    pero algunas cantidades aceptan más, como InvoicedQuantity con 3)."""
    fmt = f"{{:.{decimals}f}}"
    return fmt.format(value if isinstance(value, Decimal) else Decimal(str(value)))
