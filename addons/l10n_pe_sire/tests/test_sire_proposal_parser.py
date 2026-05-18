# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.sire_proposal_parser import parse_rce_txt

SAMPLE_LINE = (
    "202604|"
    "1|"
    "00000001|"
    "01|"
    "F001|"
    "123|"
    "15/04/2026|"
    "30/04/2026|"
    "6|"
    "20131312955|"
    "PROVEEDOR SAC|"
    "100.00|"
    "18.00|"
    "0.00|"
    "0.00|"
    "118.00|"
    "1.000|"
    "|"  # extra columns ignored
)


@tagged("post_install", "-at_install", "l10n_pe_sire")
class TestSireProposalParser(TransactionCase):
    def test_parses_single_line(self):
        result = parse_rce_txt(SAMPLE_LINE.encode("utf-8"))
        self.assertEqual(len(result), 1)
        line = result[0]
        self.assertEqual(line.period, "202604")
        self.assertEqual(line.doc_type_code, "01")
        self.assertEqual(line.serie, "F001")
        self.assertEqual(line.number, "123")
        self.assertEqual(line.issue_date, date(2026, 4, 15))
        self.assertEqual(line.supplier_doc_number, "20131312955")
        self.assertEqual(line.supplier_name, "PROVEEDOR SAC")
        self.assertEqual(line.total, Decimal("118.00"))

    def test_parses_multiple_lines_crlf(self):
        content = (SAMPLE_LINE + "\r\n" + SAMPLE_LINE).encode("utf-8")
        result = parse_rce_txt(content)
        self.assertEqual(len(result), 2)

    def test_skips_malformed_line(self):
        bad = "solo|tres|cols"
        content = (SAMPLE_LINE + "\n" + bad + "\n" + SAMPLE_LINE).encode("utf-8")
        result = parse_rce_txt(content)
        # 2 buenas + 1 mala (skipeada) = 2
        self.assertEqual(len(result), 2)

    def test_empty_content_returns_empty(self):
        self.assertEqual(parse_rce_txt(b""), [])

    def test_handles_comma_decimal(self):
        line = SAMPLE_LINE.replace("118.00", "118,00")
        result = parse_rce_txt(line.encode("utf-8"))
        self.assertEqual(result[0].total, Decimal("118.00"))

    def test_handles_empty_due_date(self):
        line = SAMPLE_LINE.replace("|30/04/2026|", "||")
        result = parse_rce_txt(line.encode("utf-8"))
        self.assertIsNone(result[0].due_date)
