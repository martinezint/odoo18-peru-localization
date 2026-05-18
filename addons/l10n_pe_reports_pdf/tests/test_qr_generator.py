# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.qr_generator import build_qr_data, build_qr_png_bytes


@tagged("post_install", "-at_install", "l10n_pe_reports_pdf")
class TestQrDataString(TransactionCase):
    """Tests del string canónico del QR (formato RS 097-2012)."""

    def _data(self, **overrides):
        defaults = dict(
            ruc="20131312955",
            doc_type_code="01",
            serie="F001",
            number="123",
            igv=Decimal("18.00"),
            total=Decimal("118.00"),
            issue_date=date(2026, 5, 18),
            customer_doc_type_code="6",
            customer_doc_number="20100047218",
            hash_value="ABC123==",
        )
        defaults.update(overrides)
        return build_qr_data(**defaults)

    def test_basic_format(self):
        out = self._data()
        # 10 campos separados por |
        cols = out.split("|")
        self.assertEqual(len(cols), 10)

    def test_field_order(self):
        out = self._data()
        cols = out.split("|")
        self.assertEqual(cols[0], "20131312955")  # RUC
        self.assertEqual(cols[1], "01")  # tipo doc
        self.assertEqual(cols[2], "F001")  # serie
        self.assertEqual(cols[3], "123")  # número
        self.assertEqual(cols[4], "18.00")  # IGV
        self.assertEqual(cols[5], "118.00")  # total
        self.assertEqual(cols[6], "2026-05-18")  # fecha
        self.assertEqual(cols[7], "6")  # cliente tipo doc
        self.assertEqual(cols[8], "20100047218")  # cliente número
        self.assertEqual(cols[9], "ABC123==")  # hash

    def test_leading_zeros_stripped_from_number(self):
        out = self._data(number="00000123")
        cols = out.split("|")
        self.assertEqual(cols[3], "123")

    def test_zero_number_remains_zero(self):
        out = self._data(number="0")
        cols = out.split("|")
        self.assertEqual(cols[3], "0")

    def test_amounts_two_decimals(self):
        out = self._data(igv=Decimal("18"), total=Decimal("118"))
        cols = out.split("|")
        self.assertEqual(cols[4], "18.00")
        self.assertEqual(cols[5], "118.00")

    def test_float_input_works(self):
        out = self._data(igv=18.5, total=118.5)
        cols = out.split("|")
        self.assertEqual(cols[4], "18.50")
        self.assertEqual(cols[5], "118.50")

    def test_default_customer_doc_type_when_none(self):
        out = self._data(customer_doc_type_code="")
        cols = out.split("|")
        # Si no hay tipo, default '0' (sin documento)
        self.assertEqual(cols[7], "0")

    def test_hash_value_preserved(self):
        out = self._data(hash_value="abc/def+gh==")
        cols = out.split("|")
        self.assertEqual(cols[9], "abc/def+gh==")


@tagged("post_install", "-at_install", "l10n_pe_reports_pdf")
class TestQrPngGenerator(TransactionCase):
    """Tests del renderizado PNG."""

    def test_png_starts_with_magic_bytes(self):
        png = build_qr_png_bytes("hello world")
        # PNG signature: 89 50 4E 47 0D 0A 1A 0A
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")

    def test_empty_string_still_renders(self):
        png = build_qr_png_bytes("")
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_long_string_renders(self):
        data = "|".join(
            [
                "20131312955",
                "01",
                "F001",
                "123",
                "18.00",
                "118.00",
                "2026-05-18",
                "6",
                "20100047218",
                "A" * 100,
            ]
        )
        png = build_qr_png_bytes(data)
        self.assertGreater(len(png), 100)
