# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.ple_12_1_inv_fisico import (
    OP_COMPRA,
    OP_VENTA,
    PLE_INV_FISICO_COLUMNS,
    Ple12_1Generator,
    Ple12_1Line,
    render_line,
)


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle12_1Render(TransactionCase):
    """Render unitario sin ORM."""

    def _line(self, **overrides):
        defaults = {
            "period": "20260400",
            "cuo": 1,
            "correlativo": "S00000001",
            "op_type": OP_COMPRA,
            "op_date": date(2026, 4, 15),
            "product_code": "PROD001",
            "product_name": "Producto X",
            "entry_qty": Decimal("10"),
            "balance_qty": Decimal("10"),
        }
        defaults.update(overrides)
        return Ple12_1Line(**defaults)

    def test_12_columns(self):
        cols = render_line(self._line()).split("|")
        self.assertEqual(len(cols), PLE_INV_FISICO_COLUMNS + 1)

    def test_period_in_first_col(self):
        cols = render_line(self._line()).split("|")
        self.assertEqual(cols[0], "20260400")

    def test_op_type_in_col_3(self):
        cols = render_line(self._line()).split("|")
        # cols[3] = op_type (cat 12.4)
        self.assertEqual(cols[3], OP_COMPRA)

    def test_qty_4_decimals(self):
        cols = render_line(self._line(entry_qty=Decimal("5.5"))).split("|")
        self.assertEqual(cols[8], "5.5000")

    def test_product_name_strips_pipes(self):
        cols = render_line(self._line(product_name="Pro|duc|to")).split("|")
        self.assertEqual(cols[6], "Pro duc to")


@tagged("post_install", "-at_install", "l10n_pe_ple")
class TestPle12_1Generator(TransactionCase):
    """E2E placeholder: si stock no expone moves del período, lista vacía."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Inv Fisico",
                "country_id": cls.pe.id,
                "vat": "20131312955",
            }
        )

    def test_returns_iterator_without_error(self):
        gen = Ple12_1Generator(self.env, self.company, "202604")
        lines = list(gen.iter_lines())
        # Sin stock.move done en company test, devolvemos lista (puede ser vacía)
        self.assertIsInstance(lines, list)

    def test_op_type_inference_compra(self):
        gen = Ple12_1Generator(self.env, self.company, "202604")
        op = gen._infer_op_type(
            type(
                "M",
                (),
                {
                    "picking_id": type(
                        "P", (), {"picking_type_id": type("PT", (), {"code": "incoming"})()}
                    )()
                },
            )(),
            is_in=True,
            is_out=False,
        )
        self.assertEqual(op, OP_COMPRA)

    def test_op_type_inference_venta(self):
        gen = Ple12_1Generator(self.env, self.company, "202604")
        op = gen._infer_op_type(
            type(
                "M",
                (),
                {
                    "picking_id": type(
                        "P", (), {"picking_type_id": type("PT", (), {"code": "outgoing"})()}
                    )()
                },
            )(),
            is_in=False,
            is_out=True,
        )
        self.assertEqual(op, OP_VENTA)
