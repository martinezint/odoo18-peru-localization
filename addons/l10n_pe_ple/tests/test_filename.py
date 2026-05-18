# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.tests.common import TransactionCase, tagged

from ..services.ple_filename import (
    LIBRO_COMPRAS_8_1,
    LIBRO_DIARIO_5_1,
    LIBRO_VENTAS_14_1,
    PERIODICITY_ANNUAL,
    build_ple_filename,
)


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPleFilename(TransactionCase):

    def test_ventas_basic(self):
        fn = build_ple_filename(
            ruc="20131312955",
            period_yyyymm="202604",
            libro_code=LIBRO_VENTAS_14_1,
        )
        # LE + 11 RUC + 8 período(YYYYMM00) + 6 libro + 1 oper + 1 info + 1 mon + 1 mix
        self.assertEqual(fn, "LE20131312955202604001401001111.txt")

    def test_compras_basic(self):
        fn = build_ple_filename(
            ruc="20131312955",
            period_yyyymm="202604",
            libro_code=LIBRO_COMPRAS_8_1,
        )
        self.assertEqual(fn, "LE20131312955202604000801001111.txt")

    def test_no_movements_uses_zero(self):
        fn = build_ple_filename(
            ruc="20131312955",
            period_yyyymm="202604",
            libro_code=LIBRO_VENTAS_14_1,
            has_movements=False,
            has_info=False,
        )
        # oper=0, info=0
        self.assertEqual(fn, "LE20131312955202604001401000011.txt")

    def test_dollars_currency(self):
        fn = build_ple_filename(
            ruc="20131312955",
            period_yyyymm="202604",
            libro_code=LIBRO_VENTAS_14_1,
            currency_indicator="2",
        )
        # currency=2 en penúltima posición
        self.assertEqual(fn, "LE20131312955202604001401001121.txt")

    def test_annual_period(self):
        fn = build_ple_filename(
            ruc="20131312955",
            period_yyyymm="202604",  # mes se ignora para anuales
            libro_code=LIBRO_DIARIO_5_1,
            periodicity=PERIODICITY_ANNUAL,
        )
        # Año 2026 + 12 + 00 + libro 050100 + 1 + 1 + 1 + 1
        self.assertEqual(fn, "LE20131312955202612000501001111.txt")

    # ─── Validaciones ────────────────────────────────────────────

    def test_invalid_ruc_length_raises(self):
        with self.assertRaisesRegex(ValueError, "ruc"):
            build_ple_filename(
                ruc="201313", period_yyyymm="202604",
                libro_code=LIBRO_VENTAS_14_1,
            )

    def test_invalid_periodo_length_raises(self):
        with self.assertRaisesRegex(ValueError, "period"):
            build_ple_filename(
                ruc="20131312955", period_yyyymm="20260",
                libro_code=LIBRO_VENTAS_14_1,
            )

    def test_invalid_libro_code_raises(self):
        with self.assertRaisesRegex(ValueError, "libro"):
            build_ple_filename(
                ruc="20131312955", period_yyyymm="202604", libro_code="14",
            )

    def test_invalid_currency_raises(self):
        with self.assertRaisesRegex(ValueError, "currency"):
            build_ple_filename(
                ruc="20131312955", period_yyyymm="202604",
                libro_code=LIBRO_VENTAS_14_1, currency_indicator="9",
            )
