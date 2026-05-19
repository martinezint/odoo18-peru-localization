# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador UBL 2.1 para Notas de Crédito (tipo 07) y Débito (tipo 08).

A diferencia de la Factura/Boleta (Invoice-2), las notas tienen su propio
schema raíz (CreditNote-2 / DebitNote-2) y un bloque obligatorio de
referencia al documento original que modifican:

    <cac:BillingReference>
      <cac:InvoiceDocumentReference>
        <cbc:ID>F001-123</cbc:ID>
        <cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>
      </cac:InvoiceDocumentReference>
    </cac:BillingReference>
    <cac:DiscrepancyResponse>
      <cbc:ReferenceID>F001-123</cbc:ReferenceID>
      <cbc:ResponseCode>01</cbc:ResponseCode>   <!-- Cat 09 NC / Cat 10 ND -->
      <cbc:Description>ANULACIÓN DE LA OPERACIÓN</cbc:Description>
    </cac:DiscrepancyResponse>

Catálogos SUNAT relevantes:
- Cat 09 (motivos NC): 01 Anulación, 02 Anulación por error en RUC, 03
                       Corrección por error en descripción, 04 Descuento
                       global, 05 Descuento por ítem, 06 Devolución total,
                       07 Devolución por ítem, 08 Bonificación, 09 Disminución
                       en el valor, 10 Otros conceptos, 11 Ajustes operaciones
                       de exportación, 12-13 Ajustes IVAP/ISC.
- Cat 10 (motivos ND): 01 Intereses por mora, 02 Aumento en el valor, 03
                       Penalidades / otros conceptos, 11 Ajustes operaciones
                       de exportación, 12-13 Ajustes IVAP/ISC.

Comparten con Factura: emisor/cliente, tax_total, monetary_totals, lines.
Solo cambia: root tag + namespace, header tag (CreditNoteTypeCode vs
InvoiceTypeCode), bloque BillingReference + DiscrepancyResponse, y el
nombre de las líneas (cac:CreditNoteLine / cac:DebitNoteLine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal

from lxml import etree

from . import ubl_builder
from .ubl_builder import (
    NS_CAC,
    NS_CBC,
    NS_EXT,
    InvoiceLine,
    Party,
    UblInvoiceBuilder,
    _fmt,
)

NSMAP_INVOICE = ubl_builder.NSMAP

NS_CREDIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
NS_DEBIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2"


def _ns_map(root_ns: str) -> dict:
    return {**NSMAP_INVOICE, None: root_ns}


# ─── Motivos catálogo 09/10 (selección común) ─────────────────────────
CREDIT_REASON_ANULACION = "01"
CREDIT_REASON_ERROR_RUC = "02"
CREDIT_REASON_DESCUENTO_GLOBAL = "04"
CREDIT_REASON_DEVOLUCION_TOTAL = "06"
CREDIT_REASON_OTROS = "10"

DEBIT_REASON_INTERESES_MORA = "01"
DEBIT_REASON_AUMENTO_VALOR = "02"
DEBIT_REASON_PENALIDADES = "03"


@dataclass
class BillingReference:
    """Referencia al documento original que la nota modifica."""

    serie_number: str  # "F001-123"
    doc_type_code: str = "01"  # Cat 01: 01 Factura, 03 Boleta


@dataclass
class CreditDebitNote:
    """Nota de Crédito (07) o Débito (08)."""

    serie_number: str  # "FC01-1" para NC factura, "FD01-1" para ND factura
    issue_date: date
    issue_time: time
    is_credit: bool = True  # True → NC (07), False → ND (08)
    reason_code: str = "01"  # Cat 09 (NC) / Cat 10 (ND)
    reason_description: str = "ANULACIÓN DE LA OPERACIÓN"

    billing_reference: BillingReference = field(default_factory=lambda: BillingReference(""))
    currency_code: str = "PEN"
    note_amount_in_words: str = ""

    supplier: Party = field(default_factory=lambda: Party("", "6", ""))
    customer: Party = field(default_factory=lambda: Party("", "6", ""))

    lines: list[InvoiceLine] = field(default_factory=list)

    total_igv: Decimal = Decimal("0")
    total_taxed: Decimal = Decimal("0")
    total_line_extension: Decimal = Decimal("0")
    total_payable: Decimal = Decimal("0")
    total_tax_exclusive: Decimal = Decimal("0")
    total_tax_inclusive: Decimal = Decimal("0")


class UblCreditDebitNoteBuilder:
    """Construye <CreditNote> o <DebitNote> SUNAT desde un CreditDebitNote."""

    def build(self, note: CreditDebitNote) -> etree._Element:
        root_ns = NS_CREDIT_NOTE if note.is_credit else NS_DEBIT_NOTE
        root_tag = "CreditNote" if note.is_credit else "DebitNote"
        root = etree.Element(f"{{{root_ns}}}{root_tag}", nsmap=_ns_map(root_ns))

        self._add_extensions(root)
        self._add_header(root, note)
        self._add_billing_reference(root, note.billing_reference)
        self._add_discrepancy_response(root, note)
        self._add_signature_block(root, note)
        # Reusamos los bloques party + tax + totals del builder de Invoice
        inv_builder = UblInvoiceBuilder()
        inv_builder._add_party(root, note.supplier, "AccountingSupplierParty")
        inv_builder._add_party(root, note.customer, "AccountingCustomerParty")
        self._add_tax_total(root, note)
        self._add_monetary_totals(root, note)
        self._add_lines(root, note)

        return root

    def build_xml_bytes(self, note: CreditDebitNote) -> bytes:
        return etree.tostring(
            self.build(note),
            xml_declaration=True,
            encoding="UTF-8",
            standalone=False,
        )

    # ─── Bloques específicos de notas ─────────────────────────────────

    def _add_extensions(self, root):
        exts = etree.SubElement(root, f"{{{NS_EXT}}}UBLExtensions")
        ext = etree.SubElement(exts, f"{{{NS_EXT}}}UBLExtension")
        etree.SubElement(ext, f"{{{NS_EXT}}}ExtensionContent")

    def _add_header(self, root, note: CreditDebitNote):
        self._cbc(root, "UBLVersionID", "2.1")
        self._cbc(root, "CustomizationID", "2.0")
        self._cbc(root, "ID", note.serie_number)
        self._cbc(root, "IssueDate", note.issue_date.isoformat())
        self._cbc(root, "IssueTime", note.issue_time.isoformat())
        if note.note_amount_in_words:
            self._cbc(root, "Note", note.note_amount_in_words, languageLocaleID="1000")
        self._cbc(root, "DocumentCurrencyCode", note.currency_code)

    def _add_billing_reference(self, root, ref: BillingReference):
        br = etree.SubElement(root, f"{{{NS_CAC}}}BillingReference")
        idr = etree.SubElement(br, f"{{{NS_CAC}}}InvoiceDocumentReference")
        self._cbc(idr, "ID", ref.serie_number)
        self._cbc(
            idr,
            "DocumentTypeCode",
            ref.doc_type_code,
            listAgencyName="PE:SUNAT",
            listName="Tipo de Documento",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01",
        )

    def _add_discrepancy_response(self, root, note: CreditDebitNote):
        dr = etree.SubElement(root, f"{{{NS_CAC}}}DiscrepancyResponse")
        self._cbc(dr, "ReferenceID", note.billing_reference.serie_number)
        listname = "Tipo de nota de crédito" if note.is_credit else "Tipo de nota de débito"
        cat = "09" if note.is_credit else "10"
        self._cbc(
            dr,
            "ResponseCode",
            note.reason_code,
            listAgencyName="PE:SUNAT",
            listName=listname,
            listURI=f"urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo{cat}",
        )
        self._cbc(dr, "Description", note.reason_description)

    def _add_signature_block(self, root, note: CreditDebitNote):
        sig = etree.SubElement(root, f"{{{NS_CAC}}}Signature")
        self._cbc(sig, "ID", "IDSignatureSP")
        signatory = etree.SubElement(sig, f"{{{NS_CAC}}}SignatoryParty")
        pid = etree.SubElement(signatory, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(pid, "ID", note.supplier.ruc)
        pname = etree.SubElement(signatory, f"{{{NS_CAC}}}PartyName")
        self._cbc(pname, "Name", note.supplier.legal_name)
        dsa = etree.SubElement(sig, f"{{{NS_CAC}}}DigitalSignatureAttachment")
        eref = etree.SubElement(dsa, f"{{{NS_CAC}}}ExternalReference")
        self._cbc(eref, "URI", f"#{note.supplier.ruc}-IDSignatureSP")

    def _add_tax_total(self, root, note: CreditDebitNote):
        tt = etree.SubElement(root, f"{{{NS_CAC}}}TaxTotal")
        self._cbc(tt, "TaxAmount", _fmt(note.total_igv, 2), currencyID=note.currency_code)
        subtotal = etree.SubElement(tt, f"{{{NS_CAC}}}TaxSubtotal")
        self._cbc(
            subtotal, "TaxableAmount", _fmt(note.total_taxed, 2), currencyID=note.currency_code
        )
        self._cbc(subtotal, "TaxAmount", _fmt(note.total_igv, 2), currencyID=note.currency_code)
        category = etree.SubElement(subtotal, f"{{{NS_CAC}}}TaxCategory")
        tax_scheme = etree.SubElement(category, f"{{{NS_CAC}}}TaxScheme")
        self._cbc(tax_scheme, "ID", "1000")
        self._cbc(tax_scheme, "Name", "IGV")
        self._cbc(tax_scheme, "TaxTypeCode", "VAT")

    def _add_monetary_totals(self, root, note: CreditDebitNote):
        """Para NC usa LegalMonetaryTotal; para ND usa RequestedMonetaryTotal."""
        tag = "LegalMonetaryTotal" if note.is_credit else "RequestedMonetaryTotal"
        lmt = etree.SubElement(root, f"{{{NS_CAC}}}{tag}")
        self._cbc(
            lmt,
            "LineExtensionAmount",
            _fmt(note.total_line_extension, 2),
            currencyID=note.currency_code,
        )
        self._cbc(
            lmt,
            "TaxExclusiveAmount",
            _fmt(note.total_tax_exclusive, 2),
            currencyID=note.currency_code,
        )
        self._cbc(
            lmt,
            "TaxInclusiveAmount",
            _fmt(note.total_tax_inclusive, 2),
            currencyID=note.currency_code,
        )
        self._cbc(
            lmt,
            "PayableAmount",
            _fmt(note.total_payable, 2),
            currencyID=note.currency_code,
        )

    def _add_lines(self, root, note: CreditDebitNote):
        """NC usa cac:CreditNoteLine, ND usa cac:DebitNoteLine."""
        line_tag = "CreditNoteLine" if note.is_credit else "DebitNoteLine"
        qty_tag = "CreditedQuantity" if note.is_credit else "DebitedQuantity"
        for line in note.lines:
            ln = etree.SubElement(root, f"{{{NS_CAC}}}{line_tag}")
            self._cbc(ln, "ID", str(line.line_id))
            self._cbc(ln, qty_tag, _fmt(line.quantity, 3), unitCode=line.unit_code)
            self._cbc(
                ln,
                "LineExtensionAmount",
                _fmt(line.line_extension_amount, 2),
                currencyID=note.currency_code,
            )
            # IGV de la línea
            ltt = etree.SubElement(ln, f"{{{NS_CAC}}}TaxTotal")
            self._cbc(ltt, "TaxAmount", _fmt(line.igv_amount, 2), currencyID=note.currency_code)
            lts = etree.SubElement(ltt, f"{{{NS_CAC}}}TaxSubtotal")
            self._cbc(
                lts,
                "TaxableAmount",
                _fmt(line.line_extension_amount, 2),
                currencyID=note.currency_code,
            )
            self._cbc(lts, "TaxAmount", _fmt(line.igv_amount, 2), currencyID=note.currency_code)
            cat = etree.SubElement(lts, f"{{{NS_CAC}}}TaxCategory")
            self._cbc(cat, "Percent", _fmt(line.igv_percentage, 2))
            self._cbc(
                cat,
                "TaxExemptionReasonCode",
                line.igv_affectation_code,
                listAgencyName="PE:SUNAT",
                listName="Afectación del IGV",
                listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07",
            )
            scheme = etree.SubElement(cat, f"{{{NS_CAC}}}TaxScheme")
            self._cbc(scheme, "ID", "1000")
            self._cbc(scheme, "Name", "IGV")
            self._cbc(scheme, "TaxTypeCode", "VAT")
            # Item + price
            item = etree.SubElement(ln, f"{{{NS_CAC}}}Item")
            self._cbc(item, "Description", line.description)
            price = etree.SubElement(ln, f"{{{NS_CAC}}}Price")
            self._cbc(price, "PriceAmount", _fmt(line.unit_price, 6), currencyID=note.currency_code)

    def _cbc(self, parent, tag: str, text: str, **attrs):
        el = etree.SubElement(parent, f"{{{NS_CBC}}}{tag}")
        for k, v in attrs.items():
            el.set(k, v)
        if text is not None:
            el.text = text
        return el
