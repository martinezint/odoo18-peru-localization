# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador PLE 13.1 — Registro de Inventario Permanente Valorizado.

Itera `stock.valuation.layer` del período. Cada layer representa un
movimiento valorizado (cantidad × costo unitario) generado por:
- Compra recibida (signo +)
- Venta enviada (signo -)
- Devolución
- Ajuste de inventario
- Producción

Estructura SUNAT Anexo 13.1 (versión simplificada):
  1. Período (YYYYMM00)
  2. CUO
  3. Correlativo
  4. Tipo operación (Cat 12.4)
  5. Fecha de la operación
  6. Código del producto
  7. Descripción
  8. UM SUNAT (cat 03)
  9. Cantidad entrada
 10. Costo unitario entrada (4 decimales)
 11. Costo total entrada (2 decimales)
 12. Cantidad salida
 13. Costo unitario salida
 14. Costo total salida
 15. Saldo cantidad
 16. Saldo costo unitario
 17. Saldo costo total
 18. Estado: '1' inicial, '8' ajuste, '9' anulado

Total: 18 columnas.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PLE_INV_VAL_COLUMNS = 18

OP_INV_INICIAL = "01"
OP_COMPRA = "02"
OP_VENTA = "06"
OP_TRANSFER = "10"
OP_AJUSTE = "16"


@dataclass
class Ple13_1Line:
    period: str
    cuo: int
    correlativo: str
    op_type: str
    op_date: date
    product_code: str
    product_name: str
    unit_code: str = "NIU"
    entry_qty: Decimal = Decimal("0")
    entry_unit_cost: Decimal = Decimal("0")
    entry_total_cost: Decimal = Decimal("0")
    exit_qty: Decimal = Decimal("0")
    exit_unit_cost: Decimal = Decimal("0")
    exit_total_cost: Decimal = Decimal("0")
    balance_qty: Decimal = Decimal("0")
    balance_unit_cost: Decimal = Decimal("0")
    balance_total_cost: Decimal = Decimal("0")
    state: str = "1"


def render_line(line: Ple13_1Line) -> str:
    cols = [
        line.period,
        str(line.cuo),
        line.correlativo,
        line.op_type,
        _fmt_date(line.op_date),
        line.product_code,
        _clean(line.product_name),
        line.unit_code,
        _fmt_qty(line.entry_qty),
        _fmt_amt4(line.entry_unit_cost),
        _fmt_amt2(line.entry_total_cost),
        _fmt_qty(line.exit_qty),
        _fmt_amt4(line.exit_unit_cost),
        _fmt_amt2(line.exit_total_cost),
        _fmt_qty(line.balance_qty),
        _fmt_amt4(line.balance_unit_cost),
        _fmt_amt2(line.balance_total_cost),
        line.state,
    ]
    return "|".join(cols) + "|"


class Ple13_1Generator:
    """Itera líneas TXT del Inventario Valorizado desde stock.valuation.layer."""

    def __init__(self, env, company, period_yyyymm: str):
        self.env = env
        self.company = company
        self.period = f"{period_yyyymm}00"
        self.period_yyyymm = period_yyyymm

    def iter_lines(self) -> Iterator[str]:
        Layer = self.env.get("stock.valuation.layer")
        if Layer is None:
            return  # stock_account no instalado
        year = int(self.period_yyyymm[:4])
        month = int(self.period_yyyymm[4:])
        date_from = date(year, month, 1)
        date_to = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        layers = Layer.search(
            [
                ("company_id", "=", self.company.id),
                ("create_date", ">=", date_from),
                ("create_date", "<", date_to),
            ],
            order="product_id, create_date, id",
        )
        # Saldos acumulados por producto: (qty, total_value)
        balances: dict[int, tuple[Decimal, Decimal]] = {}
        for cuo, layer in enumerate(layers, start=1):
            yield render_line(self._layer_to_line(layer, cuo=cuo, balances=balances))

    def generate_to_file(self, fobj) -> int:
        count = 0
        for txt in self.iter_lines():
            fobj.write((txt + "\r\n").encode("utf-8"))
            count += 1
        return count

    def _layer_to_line(self, layer, *, cuo: int, balances: dict) -> Ple13_1Line:
        qty = Decimal(str(layer.quantity or 0))
        value = Decimal(str(layer.value or 0))
        is_in = qty > 0
        is_out = qty < 0
        entry_qty = qty if is_in else Decimal("0")
        entry_val = value if is_in else Decimal("0")
        exit_qty = abs(qty) if is_out else Decimal("0")
        exit_val = abs(value) if is_out else Decimal("0")
        entry_unit = (entry_val / entry_qty) if entry_qty else Decimal("0")
        exit_unit = (exit_val / exit_qty) if exit_qty else Decimal("0")

        pid = layer.product_id.id
        prev_qty, prev_val = balances.get(pid, (Decimal("0"), Decimal("0")))
        new_qty = prev_qty + qty
        new_val = prev_val + value
        new_unit = (new_val / new_qty) if new_qty else Decimal("0")
        balances[pid] = (new_qty, new_val)

        return Ple13_1Line(
            period=self.period,
            cuo=cuo,
            correlativo=f"V{layer.id:08d}",
            op_type=self._infer_op_type(layer, is_in=is_in, is_out=is_out),
            op_date=layer.create_date.date() if layer.create_date else date.today(),
            product_code=(layer.product_id.default_code or f"P{layer.product_id.id}").strip(),
            product_name=layer.product_id.name or "",
            unit_code="NIU",
            entry_qty=entry_qty,
            entry_unit_cost=entry_unit,
            entry_total_cost=entry_val,
            exit_qty=exit_qty,
            exit_unit_cost=exit_unit,
            exit_total_cost=exit_val,
            balance_qty=new_qty,
            balance_unit_cost=new_unit,
            balance_total_cost=new_val,
            state="1",
        )

    @staticmethod
    def _infer_op_type(layer, *, is_in: bool, is_out: bool) -> str:
        # stock_move_id puede indicar el tipo
        if layer.stock_move_id:
            ptype = (
                layer.stock_move_id.picking_type_id.code if layer.stock_move_id.picking_id else ""
            )
            if ptype == "incoming":
                return OP_COMPRA
            if ptype == "outgoing":
                return OP_VENTA
            if ptype == "internal":
                return OP_TRANSFER
        if is_in:
            return OP_COMPRA
        if is_out:
            return OP_VENTA
        return OP_AJUSTE


def _fmt_qty(value, decimals: int = 4) -> str:
    if value is None:
        return f"{Decimal('0'):.{decimals}f}"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.{decimals}f}"


def _fmt_amt2(value) -> str:
    if value is None:
        return "0.00"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.2f}"


def _fmt_amt4(value) -> str:
    if value is None:
        return "0.0000"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.4f}"


def _fmt_date(d) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _clean(s: str) -> str:
    if not s:
        return ""
    return s.replace("|", " ").strip()
