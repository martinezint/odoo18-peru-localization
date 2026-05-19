# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date

from lxml import etree
from odoo.tests.common import TransactionCase, tagged

from ..services.ubl_builder import Party
from ..services.ubl_voided_docs_builder import (
    NS_VOIDED,
    UblVoidedDocsBuilder,
    VoidedDocuments,
    VoidedLine,
    build_cdb_file_id,
)


def _build_cdb():
    return VoidedDocuments(
        file_id="RA-20260518-1",
        reference_date=date(2026, 5, 15),
        issue_date=date(2026, 5, 18),
        supplier=Party(ruc="20131312955", doc_type_code="6", legal_name="EMISOR SAC"),
        lines=[
            VoidedLine(
                line_id=1,
                doc_type_code="01",
                serie="F001",
                number="123",
                void_reason="ERROR EN DATOS DEL CLIENTE",
            ),
            VoidedLine(
                line_id=2,
                doc_type_code="07",
                serie="FC01",
                number="5",
                void_reason="Duplicado",
            ),
        ],
    )


@tagged("post_install", "-at_install", "l10n_pe_edi")
class TestVoidedDocsBuilder(TransactionCase):
    """Comunicación de Baja (CDB) UBL builder."""

    def test_root_is_voided_documents(self):
        root = UblVoidedDocsBuilder().build(_build_cdb())
        self.assertEqual(root.tag, f"{{{NS_VOIDED}}}VoidedDocuments")

    def test_file_id_in_header(self):
        xml = UblVoidedDocsBuilder().build_xml_bytes(_build_cdb())
        tree = etree.fromstring(xml)
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        # cbc:ID es el segundo cbc en el root (después de UBLVersionID + CustomizationID)
        ids = tree.findall("./cbc:ID", namespaces=ns)
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0].text, "RA-20260518-1")

    def test_two_lines_emitted(self):
        xml = UblVoidedDocsBuilder().build_xml_bytes(_build_cdb())
        tree = etree.fromstring(xml)
        ns = {"sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"}
        lines = tree.findall(".//sac:VoidedDocumentsLine", namespaces=ns)
        self.assertEqual(len(lines), 2)

    def test_line_contains_serie_number_reason(self):
        xml = UblVoidedDocsBuilder().build_xml_bytes(_build_cdb())
        tree = etree.fromstring(xml)
        ns = {
            "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }
        line = tree.find(".//sac:VoidedDocumentsLine", namespaces=ns)
        self.assertEqual(line.findtext("sac:DocumentSerialID", namespaces=ns), "F001")
        self.assertEqual(line.findtext("sac:DocumentNumberID", namespaces=ns), "123")
        self.assertEqual(line.findtext("cbc:DocumentTypeCode", namespaces=ns), "01")
        self.assertEqual(
            line.findtext("cbc:VoidReasonDescription", namespaces=ns),
            "ERROR EN DATOS DEL CLIENTE",
        )

    def test_reference_date_is_doc_date(self):
        """ReferenceDate = fecha del comprobante anulado, NO del CDB."""
        xml = UblVoidedDocsBuilder().build_xml_bytes(_build_cdb())
        tree = etree.fromstring(xml)
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        ref = tree.findtext("./cbc:ReferenceDate", namespaces=ns)
        self.assertEqual(ref, "2026-05-15")  # fecha emisión doc original
        iss = tree.findtext("./cbc:IssueDate", namespaces=ns)
        self.assertEqual(iss, "2026-05-18")  # fecha del CDB

    def test_build_cdb_file_id_format(self):
        self.assertEqual(
            build_cdb_file_id(date(2026, 5, 18), 1),
            "RA-20260518-1",
        )
        self.assertEqual(
            build_cdb_file_id(date(2026, 12, 1), 42),
            "RA-20261201-42",
        )
