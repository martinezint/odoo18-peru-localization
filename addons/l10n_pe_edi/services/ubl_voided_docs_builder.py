# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador UBL 2.0 para Comunicación de Baja (CDB) SUNAT.

La CDB se usa para ANULAR comprobantes electrónicos (facturas, NC, ND,
guías, retenciones, percepciones) ya enviados y aceptados por SUNAT.

Se envía via SOAP `sendSummary` (asíncrono con ticket).

Estructura UBL 2.0 namespace especial:

    <VoidedDocuments xmlns="urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1"
                     xmlns:cbc="..." xmlns:cac="..." xmlns:sac="..." xmlns:ext="...">
      <ext:UBLExtensions>...</ext:UBLExtensions>
      <cbc:UBLVersionID>2.0</cbc:UBLVersionID>
      <cbc:CustomizationID>1.0</cbc:CustomizationID>
      <cbc:ID>RA-20260518-1</cbc:ID>             <!-- ID interno del archivo -->
      <cbc:ReferenceDate>2026-05-15</cbc:ReferenceDate>  <!-- fecha emisión del doc anulado -->
      <cbc:IssueDate>2026-05-18</cbc:IssueDate>            <!-- fecha del CDB -->
      <cac:Signature>...</cac:Signature>
      <cac:AccountingSupplierParty>...</cac:AccountingSupplierParty>
      <sac:VoidedDocumentsLine>+
        <cbc:LineID>1</cbc:LineID>
        <cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>  <!-- 01 fact, 03 bol, 07 NC, 08 ND, 20 ret, 40 perc -->
        <sac:DocumentSerialID>F001</sac:DocumentSerialID>
        <sac:DocumentNumberID>123</sac:DocumentNumberID>
        <cbc:VoidReasonDescription>ERROR EN DATOS DEL CLIENTE</cbc:VoidReasonDescription>
      </sac:VoidedDocumentsLine>
    </VoidedDocuments>

Convención del ID del archivo (Manual del Programador):
    RA-{YYYYMMDD}-{secuencial}  (RA = Reversa/Anulación)
    Ej: RA-20260518-1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from lxml import etree

from .ubl_builder import NS_CAC, NS_CBC, NS_EXT, Party

NS_VOIDED = "urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1"
NS_SAC = "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"

NSMAP_VOIDED = {
    None: NS_VOIDED,
    "cbc": NS_CBC,
    "cac": NS_CAC,
    "ext": NS_EXT,
    "sac": NS_SAC,
    "ds": NS_DS,
}


@dataclass
class VoidedLine:
    """Una línea = un comprobante a anular."""

    line_id: int
    doc_type_code: str  # Cat 01: '01' factura, '03' boleta, '07' NC, '08' ND, '20' ret, '40' perc
    serie: str  # 'F001'
    number: str  # '123'
    void_reason: str  # texto libre


@dataclass
class VoidedDocuments:
    """Comunicación de Baja (CDB) SUNAT."""

    file_id: str  # 'RA-20260518-1'
    reference_date: date  # fecha emisión del documento anulado
    issue_date: date  # fecha emisión del CDB
    supplier: Party = field(default_factory=lambda: Party("", "6", ""))
    lines: list[VoidedLine] = field(default_factory=list)


class UblVoidedDocsBuilder:
    """Construye <VoidedDocuments> SUNAT desde una VoidedDocuments dataclass."""

    def build(self, doc: VoidedDocuments) -> etree._Element:
        root = etree.Element(f"{{{NS_VOIDED}}}VoidedDocuments", nsmap=NSMAP_VOIDED)
        self._add_extensions(root)
        self._add_header(root, doc)
        self._add_signature_block(root, doc)
        self._add_supplier(root, doc.supplier)
        for line in doc.lines:
            self._add_line(root, line)
        return root

    def build_xml_bytes(self, doc: VoidedDocuments) -> bytes:
        return etree.tostring(
            self.build(doc),
            xml_declaration=True,
            encoding="UTF-8",
            standalone=False,
        )

    def _add_extensions(self, root):
        exts = etree.SubElement(root, f"{{{NS_EXT}}}UBLExtensions")
        ext = etree.SubElement(exts, f"{{{NS_EXT}}}UBLExtension")
        etree.SubElement(ext, f"{{{NS_EXT}}}ExtensionContent")

    def _add_header(self, root, doc: VoidedDocuments):
        self._cbc(root, "UBLVersionID", "2.0")
        self._cbc(root, "CustomizationID", "1.0")
        self._cbc(root, "ID", doc.file_id)
        self._cbc(root, "ReferenceDate", doc.reference_date.isoformat())
        self._cbc(root, "IssueDate", doc.issue_date.isoformat())

    def _add_signature_block(self, root, doc: VoidedDocuments):
        sig = etree.SubElement(root, f"{{{NS_CAC}}}Signature")
        self._cbc(sig, "ID", doc.supplier.ruc)
        sp = etree.SubElement(sig, f"{{{NS_CAC}}}SignatoryParty")
        pid = etree.SubElement(sp, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(pid, "ID", doc.supplier.ruc)
        pname = etree.SubElement(sp, f"{{{NS_CAC}}}PartyName")
        self._cbc(pname, "Name", doc.supplier.legal_name)
        dsa = etree.SubElement(sig, f"{{{NS_CAC}}}DigitalSignatureAttachment")
        eref = etree.SubElement(dsa, f"{{{NS_CAC}}}ExternalReference")
        self._cbc(eref, "URI", f"#{doc.supplier.ruc}-IDSignatureSP")

    def _add_supplier(self, root, party: Party):
        wrapper = etree.SubElement(root, f"{{{NS_CAC}}}AccountingSupplierParty")
        self._cbc(wrapper, "CustomerAssignedAccountID", party.ruc)
        self._cbc(wrapper, "AdditionalAccountID", party.doc_type_code)
        party_el = etree.SubElement(wrapper, f"{{{NS_CAC}}}Party")
        legal = etree.SubElement(party_el, f"{{{NS_CAC}}}PartyLegalEntity")
        self._cbc(legal, "RegistrationName", party.legal_name)

    def _add_line(self, root, line: VoidedLine):
        ln = etree.SubElement(root, f"{{{NS_SAC}}}VoidedDocumentsLine")
        self._cbc(ln, "LineID", str(line.line_id))
        self._cbc(
            ln,
            "DocumentTypeCode",
            line.doc_type_code,
            listAgencyName="PE:SUNAT",
            listName="Tipo de Documento",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01",
        )
        # cbc → cuando van bajo CommonBasicComponents
        sac_serial = etree.SubElement(ln, f"{{{NS_SAC}}}DocumentSerialID")
        sac_serial.text = line.serie
        sac_num = etree.SubElement(ln, f"{{{NS_SAC}}}DocumentNumberID")
        sac_num.text = line.number
        self._cbc(ln, "VoidReasonDescription", line.void_reason)

    def _cbc(self, parent, tag: str, text: str, **attrs):
        el = etree.SubElement(parent, f"{{{NS_CBC}}}{tag}")
        for k, v in attrs.items():
            el.set(k, v)
        if text is not None:
            el.text = text
        return el


# ─── Helpers ──────────────────────────────────────────────────────────


def build_cdb_file_id(reference_date: date, sequence: int) -> str:
    """Genera el ID de archivo CDB según convención SUNAT.

    Formato: RA-YYYYMMDD-N
    Ej: RA-20260518-1
    """
    return f"RA-{reference_date.strftime('%Y%m%d')}-{sequence}"
