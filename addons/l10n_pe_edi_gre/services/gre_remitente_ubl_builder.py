# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador UBL DespatchAdvice para GRE Remitente (SUNAT cat 01 tipo 09).

GRE 2.0 Remitente: documento que emite el remitente (vendedor/origen) para
amparar el traslado de mercadería. Estructura UBL 2.1 con namespace
DespatchAdvice-2 y customización SUNAT 2.0.

Estructura mínima aceptada por SUNAT:

    <DespatchAdvice xmlns="urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2"
                    xmlns:cbc="..." xmlns:cac="..." xmlns:ext="..."
                    xmlns:sac="..." xmlns:ds="...">
      <ext:UBLExtensions>...</ext:UBLExtensions>
      <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
      <cbc:CustomizationID>2.0</cbc:CustomizationID>
      <cbc:ID>T001-1</cbc:ID>
      <cbc:IssueDate>2026-05-18</cbc:IssueDate>
      <cbc:IssueTime>10:30:00</cbc:IssueTime>
      <cbc:DespatchAdviceTypeCode>09</cbc:DespatchAdviceTypeCode>
      <cac:Signature>...</cac:Signature>
      <cac:OrderReference>...</cac:OrderReference>      (opcional)
      <cac:DespatchSupplierParty>+                       <!-- emisor (remitente) -->
      <cac:DeliveryCustomerParty>+                       <!-- destinatario -->
      <cac:Shipment>
        <cbc:ID>SUNAT_Envio</cbc:ID>
        <cbc:HandlingCode>01</cbc:HandlingCode>          <!-- catálogo 20 motivo -->
        <cbc:Information>VENTA</cbc:Information>
        <cbc:GrossWeightMeasure unitCode="KGM">100.00</cbc:GrossWeightMeasure>
        <cbc:TotalTransportHandlingUnitQuantity>1</cbc:TotalTransportHandlingUnitQuantity>
        <cbc:SplitConsignmentIndicator>false</cbc:SplitConsignmentIndicator>
        <cac:ShipmentStage>
          <cbc:TransportModeCode>02</cbc:TransportModeCode>   <!-- 01 público 02 privado -->
          <cac:TransitPeriod><cbc:StartDate>2026-05-18</cbc:StartDate></cac:TransitPeriod>
          <cac:CarrierParty>+                                <!-- transportista (público) o emisor -->
          <cac:TransportMeans><cac:RoadTransport><cbc:LicensePlateID>...</cbc:LicensePlateID></cac:RoadTransport></cac:TransportMeans>
          <cac:DriverPerson><cbc:ID schemeID="1">12345678</cbc:ID></cac:DriverPerson>
        </cac:ShipmentStage>
        <cac:Delivery>
          <cac:DeliveryAddress><cbc:ID>150101</cbc:ID></cac:DeliveryAddress>
        </cac:Delivery>
        <cac:OriginAddress><cbc:ID>150122</cbc:ID></cac:OriginAddress>
      </cac:Shipment>
      <cac:DespatchLine>+
        <cbc:ID>1</cbc:ID>
        <cbc:DeliveredQuantity unitCode="NIU">2</cbc:DeliveredQuantity>
        <cac:OrderLineReference><cbc:LineID>1</cbc:LineID></cac:OrderLineReference>
        <cac:Item>
          <cbc:Description>Producto X</cbc:Description>
          <cac:SellersItemIdentification><cbc:ID>PROD001</cbc:ID></cac:SellersItemIdentification>
        </cac:Item>
      </cac:DespatchLine>
    </DespatchAdvice>

Catálogos SUNAT relevantes:
- 18: Modalidad transporte (01 público / 02 privado)
- 20: Motivo traslado (01 Venta, 02 Compra, 04 Traslado entre estab. del mismo
                         contribuyente, 09 Importación, 13 Otros, ...)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal

from lxml import etree


NS_DESPATCH = "urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_SAC = "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"

NSMAP_DESPATCH = {
    None: NS_DESPATCH,
    "cbc": NS_CBC,
    "cac": NS_CAC,
    "ext": NS_EXT,
    "ds": NS_DS,
    "sac": NS_SAC,
}


# Modalidades de transporte (cat 18)
TRANSPORT_MODE_PUBLIC = "01"
TRANSPORT_MODE_PRIVATE = "02"

# Motivos de traslado (cat 20) — selección común
MOTIVO_VENTA = "01"
MOTIVO_COMPRA = "02"
MOTIVO_TRASLADO_ESTABLECIMIENTOS = "04"
MOTIVO_IMPORTACION = "08"
MOTIVO_OTROS = "13"


@dataclass
class Party:
    """Emisor / destinatario / transportista / vendedor."""
    ruc: str
    doc_type_code: str  # cat 06: '6' RUC, '1' DNI
    legal_name: str


@dataclass
class Address:
    """Dirección con ubigeo SUNAT (6 dígitos)."""
    ubigeo: str = ""             # Ej. '150101'
    street: str = ""
    address_type_code: str = ""  # opcional, código de tipo establecimiento


@dataclass
class ShipmentStage:
    """Etapa del envío con modalidad de transporte."""
    transport_mode: str = TRANSPORT_MODE_PRIVATE
    transit_start_date: date = None  # type: ignore
    carrier_ruc: str = ""             # transportista (para público) o emisor (privado)
    carrier_name: str = ""
    license_plate: str = ""           # placa del vehículo
    driver_doc_type: str = "1"        # cat 06
    driver_doc_number: str = ""       # DNI o equivalente


@dataclass
class DespatchLine:
    """Línea de la guía: ítem que se traslada."""
    line_id: int
    description: str
    quantity: Decimal
    unit_code: str = "NIU"
    item_code: str = ""               # SKU/código interno


@dataclass
class GreRemitente:
    """Guía de Remisión Electrónica Remitente."""
    serie_number: str                 # 'T001-1'
    issue_date: date
    issue_time: time
    doc_type_code: str = "09"         # cat 01: 09 GRE Remitente

    supplier: Party = field(default_factory=lambda: Party("", "6", ""))      # Emisor/Remitente
    customer: Party = field(default_factory=lambda: Party("", "6", ""))      # Destinatario

    motivo_traslado: str = MOTIVO_VENTA            # cat 20
    motivo_descripcion: str = ""                   # texto libre acompaña al code
    gross_weight: Decimal = Decimal("0.000")        # KGM
    total_packages: int = 0
    split_consignment: bool = False

    stage: ShipmentStage = field(default_factory=ShipmentStage)

    origin: Address = field(default_factory=Address)
    delivery: Address = field(default_factory=Address)

    lines: list[DespatchLine] = field(default_factory=list)


class GreRemitenteUblBuilder:
    """Construye <DespatchAdvice> SUNAT desde un GreRemitente."""

    def build(self, gre: GreRemitente) -> etree._Element:
        root = etree.Element(f"{{{NS_DESPATCH}}}DespatchAdvice", nsmap=NSMAP_DESPATCH)
        self._add_extensions(root)
        self._add_header(root, gre)
        self._add_signature_block(root, gre)
        self._add_supplier(root, gre.supplier)
        self._add_customer(root, gre.customer)
        self._add_shipment(root, gre)
        for line in gre.lines:
            self._add_line(root, line)
        return root

    def build_xml_bytes(self, gre: GreRemitente) -> bytes:
        return etree.tostring(
            self.build(gre),
            xml_declaration=True, encoding="UTF-8", standalone=False,
        )

    def _add_extensions(self, root):
        exts = etree.SubElement(root, f"{{{NS_EXT}}}UBLExtensions")
        ext = etree.SubElement(exts, f"{{{NS_EXT}}}UBLExtension")
        etree.SubElement(ext, f"{{{NS_EXT}}}ExtensionContent")

    def _add_header(self, root, gre: GreRemitente):
        self._cbc(root, "UBLVersionID", "2.1")
        self._cbc(root, "CustomizationID", "2.0")
        self._cbc(root, "ID", gre.serie_number)
        self._cbc(root, "IssueDate", gre.issue_date.isoformat())
        self._cbc(root, "IssueTime", gre.issue_time.isoformat())
        self._cbc(
            root, "DespatchAdviceTypeCode", gre.doc_type_code,
            listAgencyName="PE:SUNAT",
            listName="Tipo de Documento",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01",
        )

    def _add_signature_block(self, root, gre: GreRemitente):
        sig = etree.SubElement(root, f"{{{NS_CAC}}}Signature")
        self._cbc(sig, "ID", gre.supplier.ruc)
        sp = etree.SubElement(sig, f"{{{NS_CAC}}}SignatoryParty")
        pid = etree.SubElement(sp, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(pid, "ID", gre.supplier.ruc)
        pname = etree.SubElement(sp, f"{{{NS_CAC}}}PartyName")
        self._cbc(pname, "Name", gre.supplier.legal_name)
        dsa = etree.SubElement(sig, f"{{{NS_CAC}}}DigitalSignatureAttachment")
        eref = etree.SubElement(dsa, f"{{{NS_CAC}}}ExternalReference")
        self._cbc(eref, "URI", f"#{gre.supplier.ruc}-IDSignatureSP")

    def _add_party_block(self, parent, party: Party, role_tag: str):
        wrapper = etree.SubElement(parent, f"{{{NS_CAC}}}{role_tag}")
        party_el = etree.SubElement(wrapper, f"{{{NS_CAC}}}Party")
        identification = etree.SubElement(party_el, f"{{{NS_CAC}}}PartyIdentification")
        self._cbc(identification, "ID", party.ruc,
                  schemeID=party.doc_type_code,
                  schemeAgencyName="PE:SUNAT",
                  schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06")
        legal = etree.SubElement(party_el, f"{{{NS_CAC}}}PartyLegalEntity")
        self._cbc(legal, "RegistrationName", party.legal_name)

    def _add_supplier(self, root, party: Party):
        self._add_party_block(root, party, "DespatchSupplierParty")

    def _add_customer(self, root, party: Party):
        self._add_party_block(root, party, "DeliveryCustomerParty")

    def _add_shipment(self, root, gre: GreRemitente):
        ship = etree.SubElement(root, f"{{{NS_CAC}}}Shipment")
        self._cbc(ship, "ID", "SUNAT_Envio")
        self._cbc(
            ship, "HandlingCode", gre.motivo_traslado,
            listAgencyName="PE:SUNAT",
            listName="Motivo de traslado",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo20",
        )
        if gre.motivo_descripcion:
            self._cbc(ship, "Information", gre.motivo_descripcion)
        self._cbc(ship, "GrossWeightMeasure", _fmt(gre.gross_weight, 3),
                  unitCode="KGM")
        self._cbc(ship, "TotalTransportHandlingUnitQuantity",
                  str(max(gre.total_packages, 1)))
        self._cbc(ship, "SplitConsignmentIndicator",
                  "true" if gre.split_consignment else "false")
        self._add_shipment_stage(ship, gre.stage)
        self._add_delivery(ship, gre.delivery)
        self._add_origin(ship, gre.origin)

    def _add_shipment_stage(self, parent, stage: ShipmentStage):
        st = etree.SubElement(parent, f"{{{NS_CAC}}}ShipmentStage")
        self._cbc(
            st, "TransportModeCode", stage.transport_mode,
            listAgencyName="PE:SUNAT",
            listName="Modalidad de Transporte",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo18",
        )
        if stage.transit_start_date:
            tp = etree.SubElement(st, f"{{{NS_CAC}}}TransitPeriod")
            self._cbc(tp, "StartDate", stage.transit_start_date.isoformat())
        if stage.carrier_ruc:
            cp = etree.SubElement(st, f"{{{NS_CAC}}}CarrierParty")
            pid = etree.SubElement(cp, f"{{{NS_CAC}}}PartyIdentification")
            self._cbc(pid, "ID", stage.carrier_ruc, schemeID="6")
            pname = etree.SubElement(cp, f"{{{NS_CAC}}}PartyName")
            self._cbc(pname, "Name", stage.carrier_name or "")
        if stage.license_plate:
            tm = etree.SubElement(st, f"{{{NS_CAC}}}TransportMeans")
            rt = etree.SubElement(tm, f"{{{NS_CAC}}}RoadTransport")
            self._cbc(rt, "LicensePlateID", stage.license_plate)
        if stage.driver_doc_number:
            dp = etree.SubElement(st, f"{{{NS_CAC}}}DriverPerson")
            self._cbc(dp, "ID", stage.driver_doc_number,
                      schemeID=stage.driver_doc_type or "1")

    def _add_delivery(self, parent, addr: Address):
        if not addr.ubigeo and not addr.street:
            return
        d = etree.SubElement(parent, f"{{{NS_CAC}}}Delivery")
        da = etree.SubElement(d, f"{{{NS_CAC}}}DeliveryAddress")
        if addr.ubigeo:
            self._cbc(da, "ID", addr.ubigeo)
        if addr.address_type_code:
            self._cbc(da, "AddressTypeCode", addr.address_type_code)
        if addr.street:
            self._cbc(da, "StreetName", addr.street)

    def _add_origin(self, parent, addr: Address):
        if not addr.ubigeo and not addr.street:
            return
        o = etree.SubElement(parent, f"{{{NS_CAC}}}OriginAddress")
        if addr.ubigeo:
            self._cbc(o, "ID", addr.ubigeo)
        if addr.address_type_code:
            self._cbc(o, "AddressTypeCode", addr.address_type_code)
        if addr.street:
            self._cbc(o, "StreetName", addr.street)

    def _add_line(self, root, line: DespatchLine):
        ln = etree.SubElement(root, f"{{{NS_CAC}}}DespatchLine")
        self._cbc(ln, "ID", str(line.line_id))
        self._cbc(ln, "DeliveredQuantity", _fmt(line.quantity, 3),
                  unitCode=line.unit_code)
        order_ref = etree.SubElement(ln, f"{{{NS_CAC}}}OrderLineReference")
        self._cbc(order_ref, "LineID", str(line.line_id))
        item = etree.SubElement(ln, f"{{{NS_CAC}}}Item")
        self._cbc(item, "Description", line.description or "Sin descripción")
        if line.item_code:
            sii = etree.SubElement(item, f"{{{NS_CAC}}}SellersItemIdentification")
            self._cbc(sii, "ID", line.item_code)

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
