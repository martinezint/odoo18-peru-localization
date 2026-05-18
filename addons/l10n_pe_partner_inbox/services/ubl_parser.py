# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Parser de comprobantes UBL 2.1 (estándar SUNAT) recibidos de proveedores.

Extrae los campos necesarios para crear un borrador de factura de compra
en Odoo. No valida la firma — eso vive en l10n_pe_edi.

UBL 2.1 estructura típica:
  <Invoice xmlns=...>
    <cbc:ID>F001-00000123</cbc:ID>
    <cbc:IssueDate>2026-05-15</cbc:IssueDate>
    <cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>PEN</cbc:DocumentCurrencyCode>
    <cac:AccountingSupplierParty>
      <cac:Party>
        <cac:PartyIdentification>
          <cbc:ID schemeID="6">20131312955</cbc:ID>  <!-- RUC -->
        </cac:PartyIdentification>
        <cac:PartyLegalEntity>
          <cbc:RegistrationName>RAZÓN SOCIAL</cbc:RegistrationName>
        </cac:PartyLegalEntity>
      </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:InvoiceLine>...</cac:InvoiceLine>+
    <cac:LegalMonetaryTotal>
      <cbc:PayableAmount currencyID="PEN">236.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
  </Invoice>
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from lxml import etree
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

UBL_NAMESPACES = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    # El namespace del documento raíz puede ser Invoice, CreditNote, DebitNote
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cn": "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
    "dn": "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2",
}


class UblParseError(UserError):
    """Error al parsear UBL — se propaga al usuario en UI."""


@dataclass
class UblInvoiceLine:
    """Línea de factura UBL parseada."""

    description: str = ""
    quantity: Decimal = Decimal("0")
    unit_code: str = "NIU"
    price_unit: Decimal = Decimal("0")
    line_extension_amount: Decimal = Decimal("0")


@dataclass
class UblInvoice:
    """Comprobante UBL 2.1 parseado.

    Soporta los 3 tipos principales: Factura (01), Boleta (03),
    Nota de Crédito (07), Nota de Débito (08).
    """

    document_number: str = ""  # e.g. "F001-00000123"
    document_type_code: str = ""  # SUNAT catálogo 01
    issue_date: date | None = None
    currency: str = "PEN"
    supplier_ruc: str = ""
    supplier_name: str = ""
    customer_ruc: str = ""
    customer_name: str = ""
    payable_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    line_extension_amount: Decimal = Decimal("0")
    lines: list[UblInvoiceLine] = field(default_factory=list)


def parse_ubl(xml_bytes: bytes) -> UblInvoice:
    """Parsea bytes UBL 2.1 → UblInvoice. Lanza UblParseError en input inválido."""
    if not xml_bytes:
        raise UblParseError(_("XML vacío."))
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise UblParseError(_("XML mal formado: %s") % exc) from exc

    return _parse_root(root)


def _parse_root(root) -> UblInvoice:
    """Extrae los campos del elemento raíz UBL."""
    invoice = UblInvoice()

    invoice.document_number = _text(root, "./cbc:ID")
    invoice.issue_date = _parse_date(_text(root, "./cbc:IssueDate"))
    invoice.document_type_code = (
        _text(root, "./cbc:InvoiceTypeCode")
        or _text(root, "./cbc:CreditNoteTypeCode")
        or _text(root, "./cbc:DebitNoteTypeCode")
    )
    invoice.currency = _text(root, "./cbc:DocumentCurrencyCode") or "PEN"

    # Supplier (proveedor que nos emite el comprobante)
    invoice.supplier_ruc = _text(
        root,
        "./cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID",
    )
    invoice.supplier_name = _text(
        root,
        "./cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName",
    )

    # Customer (nosotros)
    invoice.customer_ruc = _text(
        root,
        "./cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
    )
    invoice.customer_name = _text(
        root,
        "./cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName",
    )

    # Totales
    invoice.payable_amount = _decimal(root, "./cac:LegalMonetaryTotal/cbc:PayableAmount")
    invoice.line_extension_amount = _decimal(
        root, "./cac:LegalMonetaryTotal/cbc:LineExtensionAmount"
    )
    # TaxAmount puede aparecer en varios subelementos; tomamos el TaxTotal global.
    invoice.tax_amount = _decimal(root, "./cac:TaxTotal/cbc:TaxAmount")

    # Líneas
    line_paths = (
        "./cac:InvoiceLine",
        "./cac:CreditNoteLine",
        "./cac:DebitNoteLine",
    )
    for path in line_paths:
        for line_el in root.xpath(path, namespaces=UBL_NAMESPACES):
            invoice.lines.append(_parse_line(line_el))

    return invoice


def _parse_line(line_el) -> UblInvoiceLine:
    line = UblInvoiceLine()
    line.description = _text(line_el, "./cac:Item/cbc:Description")
    qty_el = line_el.xpath(
        "./cbc:InvoicedQuantity | ./cbc:CreditedQuantity | ./cbc:DebitedQuantity",
        namespaces=UBL_NAMESPACES,
    )
    if qty_el:
        line.quantity = Decimal(qty_el[0].text or "0")
        line.unit_code = qty_el[0].get("unitCode") or "NIU"
    line.price_unit = _decimal(line_el, "./cac:Price/cbc:PriceAmount")
    line.line_extension_amount = _decimal(line_el, "./cbc:LineExtensionAmount")
    return line


# ─── Helpers ────────────────────────────────────────────────────────


def _text(parent, xpath: str) -> str:
    """Devuelve el text del primer match o string vacío."""
    els = parent.xpath(xpath, namespaces=UBL_NAMESPACES)
    if not els:
        return ""
    el = els[0]
    return (el.text or "").strip()


def _decimal(parent, xpath: str) -> Decimal:
    text = _text(parent, xpath)
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except Exception:
        return Decimal("0")


def _parse_date(text: str) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
