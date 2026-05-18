# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador UBL DespatchAdvice para GRE Transportista (SUNAT cat 01 tipo 31).

Diferencias vs Remitente (09):

  - Emisor (DespatchSupplierParty) = TRANSPORTISTA, no el vendedor.
  - Aparece referencia al RUC del REMITENTE original que contrató al transporte.
  - El motivo es siempre "transporte público" (cat 20 código 18 — Servicio Transportista).
  - Lleva referencia al documento GRE Remitente original (`cac:AdditionalDocumentReference`).
  - El vehículo + conductor son los del transportista.

Reusa la misma estructura UBL DespatchAdvice-2 + customización SUNAT 2.0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal

from lxml import etree

from .gre_remitente_ubl_builder import (
    NS_CAC,
    NS_CBC,
    NS_DESPATCH,
    NS_EXT,
    NSMAP_DESPATCH,
    Address,
    DespatchLine,
    Party,
    _fmt,
)

# Motivo único para Transportista (cat 20 código 18)
MOTIVO_TRANSPORTE_PUBLICO = "18"


@dataclass
class RelatedRemitenteDoc:
    """Referencia al GRE Remitente original que el transportista respalda."""

    doc_type_code: str = "09"  # cat 01: 09 GRE Remitente
    serie_number: str = ""  # 'T001-123' del remitente


@dataclass
class GreTransportista:
    """Guía de Remisión Electrónica del Transportista (cat 01 tipo 31)."""

    serie_number: str  # propia del transportista, 'V001-1' por convención
    issue_date: date
    issue_time: time
    doc_type_code: str = "31"

    # Emisor = el transportista que está emitiendo este documento
    transportista: Party = field(default_factory=lambda: Party("", "6", ""))
    # Cliente del servicio: el remitente que contrató el transporte
    remitente: Party = field(default_factory=lambda: Party("", "6", ""))
    # Destinatario de la carga
    destinatario: Party = field(default_factory=lambda: Party("", "6", ""))

    # GRE Remitente original que respalda este servicio (obligatorio para SUNAT)
    related_remitente_doc: RelatedRemitenteDoc = field(default_factory=RelatedRemitenteDoc)

    gross_weight: Decimal = Decimal("0.000")  # KGM
    total_packages: int = 1
    split_consignment: bool = False

    # Vehículo + conductor son del TRANSPORTISTA
    license_plate: str = ""
    driver_doc_type: str = "1"  # cat 06: '1' DNI
    driver_doc_number: str = ""
    transit_start_date: date = None  # type: ignore

    origin: Address = field(default_factory=Address)
    delivery: Address = field(default_factory=Address)

    lines: list[DespatchLine] = field(default_factory=list)


class GreTransportistaUblBuilder:
    """Construye <DespatchAdvice> SUNAT cat 31 desde un GreTransportista."""

    def build(self, gre: GreTransportista) -> etree._Element:
        root = etree.Element(f"{{{NS_DESPATCH}}}DespatchAdvice", nsmap=NSMAP_DESPATCH)
        self._add_extensions(root)
        self._add_header(root, gre)
        self._add_signature_block(root, gre)
        self._add_related_doc_reference(root, gre.related_remitente_doc)
        self._add_party(root, gre.transportista, "DespatchSupplierParty")
        self._add_party(root, gre.destinatario, "DeliveryCustomerParty")
        # Customer real de la facturación del servicio (el remitente)
        self._add_party(root, gre.remitente, "SellerSupplierParty")
        self._add_shipment(root, gre)
        for line in gre.lines:
            self._add_line(root, line)
        return root

    def build_xml_bytes(self, gre: GreTransportista) -> bytes:
        return etree.tostring(
            self.build(gre),
            xml_declaration=True,
            encoding="UTF-8",
            standalone=False,
        )

    # ─── secciones ────────────────────────────────────────────────────

    def _add_extensions(self, root):
        exts = etree.SubElement(root, f"{{{NS_EXT}}}UBLExtensions")
        ext = etree.SubElement(exts, f"{{{NS_EXT}}}UBLExtension")
        etree.SubElement(ext, f"{{{NS_EXT}}}ExtensionContent")

    def _add_header(self, root, gre: GreTransportista):
        self._cbc(root, "UBLVersionID", "2.1")
        self._cbc(root, "CustomizationID", "2.0")
        self._cbc(root, "ID", gre.serie_number)
        self._cbc(root, "IssueDate", gre.issue_date.isoformat())
        self._cbc(root, "IssueTime", gre.issue_time.isoformat())
        self._cbc(
            root,
            "DespatchAdviceTypeCode",
            gre.doc_type_code,
            listAgencyName="PE:SUNAT",
            listName="Tipo de Documento",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01",
        )

    def _add_signature_block(self, root, gre: GreTransportista):
        sig = etree.SubElement(root, f"{{{NS_CAC}}}Signature")
        self._cbc(sig, "ID", gre.transportista.ruc)
        sp = etree.SubElement(sig, f"{{{NS_CAC}}}SignatoryParty")
        pid = etree.SubElement(sp, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(pid, "ID", gre.transportista.ruc)
        pname = etree.SubElement(sp, f"{{{NS_CAC}}}PartyName")
        self._cbc(pname, "Name", gre.transportista.legal_name)
        dsa = etree.SubElement(sig, f"{{{NS_CAC}}}DigitalSignatureAttachment")
        eref = etree.SubElement(dsa, f"{{{NS_CAC}}}ExternalReference")
        self._cbc(eref, "URI", f"#{gre.transportista.ruc}-IDSignatureSP")

    def _add_related_doc_reference(self, root, ref: RelatedRemitenteDoc):
        """Referencia al GRE Remitente original (obligatoria SUNAT cat 31)."""
        adr = etree.SubElement(root, f"{{{NS_CAC}}}AdditionalDocumentReference")
        self._cbc(adr, "ID", ref.serie_number)
        self._cbc(
            adr,
            "DocumentTypeCode",
            ref.doc_type_code,
            listAgencyName="PE:SUNAT",
            listName="Tipo de Documento",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01",
        )

    def _add_party(self, parent, party: Party, role_tag: str):
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
        legal = etree.SubElement(party_el, f"{{{NS_CAC}}}PartyLegalEntity")
        self._cbc(legal, "RegistrationName", party.legal_name)

    def _add_shipment(self, root, gre: GreTransportista):
        ship = etree.SubElement(root, f"{{{NS_CAC}}}Shipment")
        self._cbc(ship, "ID", "SUNAT_Envio")
        self._cbc(
            ship,
            "HandlingCode",
            MOTIVO_TRANSPORTE_PUBLICO,
            listAgencyName="PE:SUNAT",
            listName="Motivo de traslado",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo20",
        )
        self._cbc(ship, "GrossWeightMeasure", _fmt(gre.gross_weight, 3), unitCode="KGM")
        self._cbc(ship, "TotalTransportHandlingUnitQuantity", str(max(gre.total_packages, 1)))
        self._cbc(ship, "SplitConsignmentIndicator", "true" if gre.split_consignment else "false")
        self._add_shipment_stage(ship, gre)
        self._add_address_block(ship, gre.delivery, "Delivery")
        self._add_address_block(ship, gre.origin, "OriginAddress")

    def _add_shipment_stage(self, parent, gre: GreTransportista):
        st = etree.SubElement(parent, f"{{{NS_CAC}}}ShipmentStage")
        # Para cat 31, el modo es siempre público (01)
        self._cbc(
            st,
            "TransportModeCode",
            "01",
            listAgencyName="PE:SUNAT",
            listName="Modalidad de Transporte",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo18",
        )
        if gre.transit_start_date:
            tp = etree.SubElement(st, f"{{{NS_CAC}}}TransitPeriod")
            self._cbc(tp, "StartDate", gre.transit_start_date.isoformat())
        # Para cat 31 el CarrierParty es el propio transportista (yo)
        cp = etree.SubElement(st, f"{{{NS_CAC}}}CarrierParty")
        pid = etree.SubElement(cp, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(pid, "ID", gre.transportista.ruc, schemeID="6")
        pname = etree.SubElement(cp, f"{{{NS_CAC}}}PartyName")
        self._cbc(pname, "Name", gre.transportista.legal_name)
        # Vehículo
        if gre.license_plate:
            tm = etree.SubElement(st, f"{{{NS_CAC}}}TransportMeans")
            rt = etree.SubElement(tm, f"{{{NS_CAC}}}RoadTransport")
            self._cbc(rt, "LicensePlateID", gre.license_plate)
        # Conductor
        if gre.driver_doc_number:
            dp = etree.SubElement(st, f"{{{NS_CAC}}}DriverPerson")
            self._cbc(
                dp,
                "ID",
                gre.driver_doc_number,
                schemeID=gre.driver_doc_type,
                schemeAgencyName="PE:SUNAT",
                schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06",
            )

    def _add_address_block(self, parent, addr: Address, tag: str):
        if tag == "Delivery":
            wrapper = etree.SubElement(parent, f"{{{NS_CAC}}}Delivery")
            addr_el = etree.SubElement(wrapper, f"{{{NS_CAC}}}DeliveryAddress")
        else:
            addr_el = etree.SubElement(parent, f"{{{NS_CAC}}}{tag}")
        if addr.ubigeo:
            self._cbc(addr_el, "ID", addr.ubigeo)
        if addr.street:
            self._cbc(addr_el, "StreetName", addr.street)

    def _add_line(self, root, line: DespatchLine):
        dl = etree.SubElement(root, f"{{{NS_CAC}}}DespatchLine")
        self._cbc(dl, "ID", str(line.line_id))
        self._cbc(dl, "DeliveredQuantity", _fmt(line.quantity, 3), unitCode=line.unit_code)
        olr = etree.SubElement(dl, f"{{{NS_CAC}}}OrderLineReference")
        self._cbc(olr, "LineID", str(line.line_id))
        item = etree.SubElement(dl, f"{{{NS_CAC}}}Item")
        self._cbc(item, "Description", line.description or "Item")
        if line.item_code:
            sii = etree.SubElement(item, f"{{{NS_CAC}}}SellersItemIdentification")
            self._cbc(sii, "ID", line.item_code)

    # ─── helpers ──────────────────────────────────────────────────────

    def _cbc(self, parent, tag: str, text: str, **attrs):
        el = etree.SubElement(parent, f"{{{NS_CBC}}}{tag}")
        if attrs:
            for k, v in attrs.items():
                el.set(k, v)
        if text is not None:
            el.text = text
        return el
