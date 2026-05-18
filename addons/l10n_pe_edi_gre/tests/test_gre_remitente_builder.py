# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date, time
from decimal import Decimal

from lxml import etree
from odoo.tests.common import TransactionCase, tagged

from ..services.gre_remitente_ubl_builder import (
    MOTIVO_VENTA,
    NS_CAC,
    NS_CBC,
    NS_DESPATCH,
    NS_EXT,
    TRANSPORT_MODE_PRIVATE,
    Address,
    DespatchLine,
    GreRemitente,
    GreRemitenteUblBuilder,
    Party,
    ShipmentStage,
)


def _make_minimal_gre(line_count=1):
    g = GreRemitente(
        serie_number="T001-1",
        issue_date=date(2026, 5, 18),
        issue_time=time(10, 30, 0),
        supplier=Party(ruc="20131312955", doc_type_code="6", legal_name="EMISOR DEMO"),
        customer=Party(ruc="20100047218", doc_type_code="6", legal_name="DESTINATARIO"),
        motivo_traslado=MOTIVO_VENTA,
        motivo_descripcion="VENTA",
        gross_weight=Decimal("100.500"),
        total_packages=2,
        stage=ShipmentStage(
            transport_mode=TRANSPORT_MODE_PRIVATE,
            transit_start_date=date(2026, 5, 18),
            carrier_ruc="20131312955",
            carrier_name="EMISOR DEMO",
            license_plate="ABC-123",
            driver_doc_type="1",
            driver_doc_number="12345678",
        ),
        origin=Address(ubigeo="150122", street="AV. ORIGEN 100"),
        delivery=Address(ubigeo="150101", street="AV. DESTINO 200"),
    )
    for i in range(1, line_count + 1):
        g.lines.append(
            DespatchLine(
                line_id=i,
                description=f"Producto {i}",
                quantity=Decimal("2.000"),
                unit_code="NIU",
                item_code=f"SKU-{i}",
            )
        )
    return g


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestGreRemitenteUblBuilder(TransactionCase):
    def setUp(self):
        super().setUp()
        self.builder = GreRemitenteUblBuilder()
        self.gre = _make_minimal_gre(line_count=2)
        self.root = self.builder.build(self.gre)

    # ─── Estructura ───────────────────────────────────────────────

    def test_root_is_despatch_advice(self):
        self.assertEqual(etree.QName(self.root.tag).localname, "DespatchAdvice")
        self.assertEqual(etree.QName(self.root.tag).namespace, NS_DESPATCH)

    def test_namespaces_declared_at_root(self):
        nsmap = self.root.nsmap
        self.assertEqual(nsmap.get("cbc"), NS_CBC)
        self.assertEqual(nsmap.get("cac"), NS_CAC)
        self.assertEqual(nsmap.get("ext"), NS_EXT)

    def test_placeholder_for_signature(self):
        path = f"{{{NS_EXT}}}UBLExtensions/{{{NS_EXT}}}UBLExtension/{{{NS_EXT}}}ExtensionContent"
        self.assertIsNotNone(self.root.find(path))

    def test_header_versions_and_id(self):
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}UBLVersionID"), "2.1")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}CustomizationID"), "2.0")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}ID"), "T001-1")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}IssueDate"), "2026-05-18")
        self.assertEqual(self.root.findtext(f"{{{NS_CBC}}}IssueTime"), "10:30:00")

    def test_doc_type_code_09_with_sunat_attrs(self):
        type_el = self.root.find(f"{{{NS_CBC}}}DespatchAdviceTypeCode")
        self.assertEqual(type_el.text, "09")
        self.assertEqual(type_el.get("listAgencyName"), "PE:SUNAT")
        self.assertIn("catalogo01", type_el.get("listURI"))

    # ─── Supplier (remitente) y Customer (destinatario) ───────────

    def test_supplier_ruc(self):
        ruc = self.root.findtext(
            f"{{{NS_CAC}}}DespatchSupplierParty/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyIdentification/{{{NS_CBC}}}ID"
        )
        self.assertEqual(ruc, "20131312955")

    def test_supplier_name(self):
        name = self.root.findtext(
            f"{{{NS_CAC}}}DespatchSupplierParty/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyLegalEntity/{{{NS_CBC}}}RegistrationName"
        )
        self.assertEqual(name, "EMISOR DEMO")

    def test_customer_ruc(self):
        ruc = self.root.findtext(
            f"{{{NS_CAC}}}DeliveryCustomerParty/{{{NS_CAC}}}Party"
            f"/{{{NS_CAC}}}PartyIdentification/{{{NS_CBC}}}ID"
        )
        self.assertEqual(ruc, "20100047218")

    # ─── Shipment ────────────────────────────────────────────────

    def test_shipment_id_is_sunat_envio(self):
        self.assertEqual(
            self.root.findtext(f"{{{NS_CAC}}}Shipment/{{{NS_CBC}}}ID"),
            "SUNAT_Envio",
        )

    def test_shipment_handling_code_motivo(self):
        el = self.root.find(f"{{{NS_CAC}}}Shipment/{{{NS_CBC}}}HandlingCode")
        self.assertEqual(el.text, "01")
        self.assertIn("catalogo20", el.get("listURI"))

    def test_shipment_gross_weight(self):
        el = self.root.find(f"{{{NS_CAC}}}Shipment/{{{NS_CBC}}}GrossWeightMeasure")
        self.assertEqual(el.text, "100.500")
        self.assertEqual(el.get("unitCode"), "KGM")

    def test_shipment_total_packages(self):
        self.assertEqual(
            self.root.findtext(
                f"{{{NS_CAC}}}Shipment/{{{NS_CBC}}}TotalTransportHandlingUnitQuantity"
            ),
            "2",
        )

    def test_split_consignment_false_by_default(self):
        self.assertEqual(
            self.root.findtext(f"{{{NS_CAC}}}Shipment/{{{NS_CBC}}}SplitConsignmentIndicator"),
            "false",
        )

    # ─── ShipmentStage ───────────────────────────────────────────

    def test_transport_mode_in_stage(self):
        el = self.root.find(
            f"{{{NS_CAC}}}Shipment/{{{NS_CAC}}}ShipmentStage/{{{NS_CBC}}}TransportModeCode"
        )
        self.assertEqual(el.text, "02")  # privado
        self.assertIn("catalogo18", el.get("listURI"))

    def test_carrier_party(self):
        carrier_id = self.root.findtext(
            f"{{{NS_CAC}}}Shipment/{{{NS_CAC}}}ShipmentStage"
            f"/{{{NS_CAC}}}CarrierParty/{{{NS_CAC}}}PartyIdentification"
            f"/{{{NS_CBC}}}ID"
        )
        self.assertEqual(carrier_id, "20131312955")

    def test_license_plate_in_road_transport(self):
        plate = self.root.findtext(
            f"{{{NS_CAC}}}Shipment/{{{NS_CAC}}}ShipmentStage"
            f"/{{{NS_CAC}}}TransportMeans/{{{NS_CAC}}}RoadTransport"
            f"/{{{NS_CBC}}}LicensePlateID"
        )
        self.assertEqual(plate, "ABC-123")

    def test_driver_dni(self):
        dni_el = self.root.find(
            f"{{{NS_CAC}}}Shipment/{{{NS_CAC}}}ShipmentStage"
            f"/{{{NS_CAC}}}DriverPerson/{{{NS_CBC}}}ID"
        )
        self.assertEqual(dni_el.text, "12345678")
        self.assertEqual(dni_el.get("schemeID"), "1")

    # ─── Origin / Delivery ───────────────────────────────────────

    def test_delivery_ubigeo(self):
        ub = self.root.findtext(
            f"{{{NS_CAC}}}Shipment/{{{NS_CAC}}}Delivery/{{{NS_CAC}}}DeliveryAddress/{{{NS_CBC}}}ID"
        )
        self.assertEqual(ub, "150101")

    def test_origin_ubigeo(self):
        ub = self.root.findtext(f"{{{NS_CAC}}}Shipment/{{{NS_CAC}}}OriginAddress/{{{NS_CBC}}}ID")
        self.assertEqual(ub, "150122")

    # ─── DespatchLine ────────────────────────────────────────────

    def test_n_lines(self):
        lines = self.root.findall(f"{{{NS_CAC}}}DespatchLine")
        self.assertEqual(len(lines), 2)

    def test_line_quantity_with_unit(self):
        qty_el = self.root.find(f"{{{NS_CAC}}}DespatchLine/{{{NS_CBC}}}DeliveredQuantity")
        self.assertEqual(qty_el.text, "2.000")
        self.assertEqual(qty_el.get("unitCode"), "NIU")

    def test_line_item_description(self):
        desc = self.root.findtext(
            f"{{{NS_CAC}}}DespatchLine/{{{NS_CAC}}}Item/{{{NS_CBC}}}Description"
        )
        self.assertEqual(desc, "Producto 1")

    def test_line_seller_item_id(self):
        sku = self.root.findtext(
            f"{{{NS_CAC}}}DespatchLine/{{{NS_CAC}}}Item"
            f"/{{{NS_CAC}}}SellersItemIdentification/{{{NS_CBC}}}ID"
        )
        self.assertEqual(sku, "SKU-1")

    # ─── Serialization ───────────────────────────────────────────

    def test_serialization_well_formed(self):
        xml = self.builder.build_xml_bytes(self.gre)
        parsed = etree.fromstring(xml)
        self.assertEqual(etree.QName(parsed.tag).localname, "DespatchAdvice")


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestGreOptionalSections(TransactionCase):
    """Verifica que las secciones opcionales se omiten cuando no aplican."""

    def setUp(self):
        super().setUp()
        self.builder = GreRemitenteUblBuilder()

    def test_no_delivery_when_empty(self):
        gre = _make_minimal_gre()
        gre.delivery = Address()  # vacío
        root = self.builder.build(gre)
        self.assertIsNone(root.find(f"{{{NS_CAC}}}Shipment/{{{NS_CAC}}}Delivery"))

    def test_no_origin_when_empty(self):
        gre = _make_minimal_gre()
        gre.origin = Address()
        root = self.builder.build(gre)
        self.assertIsNone(root.find(f"{{{NS_CAC}}}Shipment/{{{NS_CAC}}}OriginAddress"))

    def test_no_seller_item_id_when_no_code(self):
        gre = _make_minimal_gre()
        gre.lines[0].item_code = ""
        root = self.builder.build(gre)
        self.assertIsNone(
            root.find(
                f"{{{NS_CAC}}}DespatchLine/{{{NS_CAC}}}Item/{{{NS_CAC}}}SellersItemIdentification"
            )
        )

    def test_no_motivo_descripcion_when_empty(self):
        gre = _make_minimal_gre()
        gre.motivo_descripcion = ""
        root = self.builder.build(gre)
        self.assertIsNone(root.find(f"{{{NS_CAC}}}Shipment/{{{NS_CBC}}}Information"))
