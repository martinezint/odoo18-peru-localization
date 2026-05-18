# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Parser de CDR (Constancia de Recepción) SUNAT.

CDR = XML ApplicationResponse UBL que SUNAT devuelve dentro de un ZIP cuando
recibe un comprobante. Contiene:
- ResponseCode: '0' aceptado, 100-1999 rechazado, 2000-3999 observado, 4000+ error
- Description: texto humano de la respuesta
- DocumentReference/ID: número del comprobante referenciado
- Notes: warnings/observaciones (códigos 2000-3999)

Estructura típica:
    <ar:ApplicationResponse xmlns:ar="urn:oasis:names:..." ...>
      <cbc:ID>some-id</cbc:ID>
      <cbc:IssueDate>2026-05-18</cbc:IssueDate>
      <cac:SenderParty>...</cac:SenderParty>
      <cac:ReceiverParty>...</cac:ReceiverParty>
      <cac:DocumentResponse>
        <cac:Response>
          <cbc:ResponseCode>0</cbc:ResponseCode>
          <cbc:Description>La Factura F001-1 ha sido aceptada</cbc:Description>
        </cac:Response>
        <cac:DocumentReference>
          <cbc:ID>F001-1</cbc:ID>
        </cac:DocumentReference>
      </cac:DocumentResponse>
      <cbc:Note>Notas/observaciones opcionales</cbc:Note>
    </ar:ApplicationResponse>
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

# Namespaces UBL ApplicationResponse
NS_AR = "urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

NSMAP = {"ar": NS_AR, "cac": NS_CAC, "cbc": NS_CBC}


@dataclass
class CdrResponse:
    """Respuesta parseada del CDR SUNAT."""

    response_code: str = ""
    description: str = ""
    document_ref: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def is_accepted(self) -> bool:
        """0 = aceptado sin observaciones."""
        return self.response_code == "0"

    @property
    def is_observed(self) -> bool:
        """2000-3999 = aceptado con observaciones (warnings)."""
        try:
            return 2000 <= int(self.response_code) < 4000
        except (TypeError, ValueError):
            return False

    @property
    def is_rejected(self) -> bool:
        """100-1999 = rechazado por SUNAT."""
        try:
            return 100 <= int(self.response_code) < 2000
        except (TypeError, ValueError):
            return False

    @property
    def is_error(self) -> bool:
        """4000+ = error técnico/sistema."""
        try:
            return int(self.response_code) >= 4000
        except (TypeError, ValueError):
            return False


class CdrParseError(Exception):
    """Error al parsear el CDR (XML mal formado o estructura inesperada)."""


def parse_cdr(xml_bytes: bytes) -> CdrResponse:
    """Parsea bytes del CDR XML → CdrResponse."""
    if not xml_bytes:
        raise CdrParseError("CDR vacío")
    try:
        tree = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise CdrParseError(f"CDR XML mal formado: {exc}") from exc

    code = _text(tree, ".//cac:DocumentResponse/cac:Response/cbc:ResponseCode")
    desc = _text(tree, ".//cac:DocumentResponse/cac:Response/cbc:Description")
    doc_ref = _text(tree, ".//cac:DocumentResponse/cac:DocumentReference/cbc:ID")
    notes = [
        n.text.strip()
        for n in tree.xpath(".//cbc:Note", namespaces=NSMAP)
        if n.text and n.text.strip()
    ]

    return CdrResponse(
        response_code=code,
        description=desc,
        document_ref=doc_ref,
        notes=notes,
    )


def _text(tree, xpath: str) -> str:
    els = tree.xpath(xpath, namespaces=NSMAP)
    if not els:
        return ""
    return (els[0].text or "").strip()
