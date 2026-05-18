# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date, time
from decimal import Decimal

from lxml import etree
from odoo.tests.common import TransactionCase, tagged

from ..services.gre_transportista_ubl_builder import (
    Address,
    DespatchLine,
    GreTransportista,
    GreTransportistaUblBuilder,
    Party,
    RelatedRemitenteDoc,
)


def _build_minimal():
    return GreTransportista(
        serie_number="V001-1",
        issue_date=date(2026, 5, 18),
        issue_time=time(10, 30, 0),
        transportista=Party(ruc="20100047234", doc_type_code="6", legal_name="TRANSPORTES SAC"),
        remitente=Party(ruc="20131312955", doc_type_code="6", legal_name="VENDEDOR SA"),
        destinatario=Party(ruc="20100047218", doc_type_code="6", legal_name="DESTINATARIO SA"),
        related_remitente_doc=RelatedRemitenteDoc(doc_type_code="09", serie_number="T001-99"),
        gross_weight=Decimal("250.500"),
        total_packages=3,
        license_plate="ABC-789",
        driver_doc_type="1",
        driver_doc_number="40404040",
        transit_start_date=date(2026, 5, 18),
        origin=Address(ubigeo="150122", street="Av. Industrial 100"),
        delivery=Address(ubigeo="150101", street="Jr. Real 200"),
        lines=[
            DespatchLine(
                line_id=1,
                description="Cajas de mercadería",
                quantity=Decimal("3"),
                unit_code="NIU",
                item_code="ITEM001",
            ),
        ],
    )


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestGreTransportistaUbl(TransactionCase):
    """Tests del builder UBL (puro Python, sin Odoo ORM)."""

    def test_root_is_despatch_advice(self):
        root = GreTransportistaUblBuilder().build(_build_minimal())
        self.assertTrue(root.tag.endswith("}DespatchAdvice"))

    def test_doc_type_code_31(self):
        xml = GreTransportistaUblBuilder().build_xml_bytes(_build_minimal())
        # Parse and find cbc:DespatchAdviceTypeCode
        tree = etree.fromstring(xml)
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        codes = tree.findall(".//cbc:DespatchAdviceTypeCode", namespaces=ns)
        self.assertEqual(len(codes), 1)
        self.assertEqual(codes[0].text, "31")

    def test_includes_reference_to_remitente_gre(self):
        xml = GreTransportistaUblBuilder().build_xml_bytes(_build_minimal())
        tree = etree.fromstring(xml)
        ns = {
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }
        adr = tree.findall(".//cac:AdditionalDocumentReference", namespaces=ns)
        self.assertEqual(len(adr), 1)
        ref_id = adr[0].findtext("cbc:ID", namespaces=ns)
        self.assertEqual(ref_id, "T001-99")
        ref_type = adr[0].findtext("cbc:DocumentTypeCode", namespaces=ns)
        self.assertEqual(ref_type, "09")

    def test_transport_mode_is_public(self):
        """Cat 31 siempre es servicio público (cod 01)."""
        xml = GreTransportistaUblBuilder().build_xml_bytes(_build_minimal())
        tree = etree.fromstring(xml)
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        modes = tree.findall(".//cbc:TransportModeCode", namespaces=ns)
        self.assertEqual(len(modes), 1)
        self.assertEqual(modes[0].text, "01")

    def test_supplier_is_transportista_ruc(self):
        xml = GreTransportistaUblBuilder().build_xml_bytes(_build_minimal())
        tree = etree.fromstring(xml)
        ns = {
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }
        supplier = tree.find(".//cac:DespatchSupplierParty", namespaces=ns)
        ruc = supplier.findtext(".//cbc:ID", namespaces=ns)
        self.assertEqual(ruc, "20100047234")  # transportista

    def test_handling_code_18_servicio_transporte(self):
        """Cat 20 motivo 18 = servicio de transporte público."""
        xml = GreTransportistaUblBuilder().build_xml_bytes(_build_minimal())
        tree = etree.fromstring(xml)
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        codes = tree.findall(".//cbc:HandlingCode", namespaces=ns)
        self.assertEqual(codes[0].text, "18")


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestGreTransportistaModel(TransactionCase):
    """Tests del modelo Odoo (validaciones, no E2E EDI)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Transportes Test SAC",
                "country_id": cls.pe.id,
                "vat": "20100047234",
            }
        )
        cls.env = cls.env(user=cls.env.user.with_company(cls.company))
        cls.remitente = cls.env["res.partner"].create(
            {"name": "Vendedor SA", "country_id": cls.pe.id, "vat": "20131312955"}
        )
        cls.dest = cls.env["res.partner"].create(
            {"name": "Destinatario SA", "country_id": cls.pe.id, "vat": "20100047218"}
        )

    def _create_gre(self, **overrides):
        defaults = {
            "name": "V001-1",
            "company_id": self.company.id,
            "remitente_partner_id": self.remitente.id,
            "destinatario_partner_id": self.dest.id,
            "related_remitente_serie_number": "T001-100",
            "gross_weight": 50.0,
            "total_packages": 2,
            "license_plate": "ABC-123",
            "driver_doc_number": "12345678",
            "origin_ubigeo": "150122",
            "destination_ubigeo": "150101",
            "line_ids": [(0, 0, {"description": "Item", "quantity": 1})],
        }
        defaults.update(overrides)
        return self.env["l10n.pe.gre.transportista"].create(defaults)

    def test_create_record(self):
        rec = self._create_gre()
        self.assertEqual(rec.state, "draft")
        self.assertEqual(len(rec.line_ids), 1)

    def test_validate_missing_ubigeo_origen(self):
        rec = self._create_gre(origin_ubigeo="123")  # 3 dígitos
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            rec._validate_required()

    def test_validate_missing_referencia_remitente(self):
        rec = self._create_gre(related_remitente_serie_number="")
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            rec._validate_required()

    def test_validate_passes_with_all_required(self):
        rec = self._create_gre()
        try:
            rec._validate_required()
        except Exception as exc:
            self.fail(f"validate no debió lanzar: {exc}")
