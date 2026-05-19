# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador PLE 12.1 — Registro de Inventario Permanente Físico (Unidades).

Itera `stock.move` con `state='done'` del período. Una línea TXT por
movimiento de stock, agrupando entradas/salidas por producto y warehouse.

Estructura SUNAT Anexo 12.1:
  1. Período (YYYYMM00)
  2. CUO
  3. Correlativo
  4. Tipo operación (Cat 12.4: 01 Inv inicial, 02 Compra, 06 Venta, ...)
  5. Fecha de la operación (DD/MM/YYYY)
  6. Código del producto (default_code o id)
  7. Descripción del producto
  8. Código unidad medida SUNAT (NIU por defecto)
  9. Entradas (cantidad)
 10. Salidas (cantidad)
 11. Saldo final (positivo)
 12. Estado: '1' inicial, '8' ajuste, '9' anulado

Total: 12 columnas separadas por '|', terminando con '|'.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PLE_INV_FISICO_COLUMNS = 12

# Catálogo SUNAT 12.4 — Tipo de Operación
OP_INV_INICIAL = "01"
OP_COMPRA = "02"
OP_VENTA = "06"
OP_TRANSFER_INTERNA = "10"
OP_AJUSTE = "16"


@dataclass
class Ple12_1Line:
    period: str
    cuo: int
    correlativo: str
    op_type: str  # cat 12.4
    op_date: date
    product_code: str
    product_name: str
    unit_code: str = "NIU"
    entry_qty: Decimal = Decimal("0")
    exit_qty: Decimal = Decimal("0")
    balance_qty: Decimal = Decimal("0")
    state: str = "1"


def render_line(line: Ple12_1Line) -> str:
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
        _fmt_qty(line.exit_qty),
        _fmt_qty(line.balance_qty),
        line.state,
    ]
    return "|".join(cols) + "|"


class Ple12_1Generator:
    """Itera líneas TXT del Inventario Permanente Físico desde stock.move done."""

    def __init__(self, env, company, period_yyyymm: str):
        self.env = env
        self.company = company
        self.period = f"{period_yyyymm}00"
        self.period_yyyymm = period_yyyymm

    def iter_lines(self) -> Iterator[str]:
        Move = self.env.get("stock.move")
        if Move is None:
            return  # módulo stock no instalado
        year = int(self.period_yyyymm[:4])
        month = int(self.period_yyyymm[4:])
        date_from = date(year, month, 1)
        date_to = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        moves = Move.search(
            [
                ("company_id", "=", self.company.id),
                ("state", "=", "done"),
                ("date", ">=", date_from),
                ("date", "<", date_to),
            ],
            order="product_id, date, id",
        )
        # Saldo acumulado por producto
        balances: dict[int, Decimal] = {}
        for cuo, mv in enumerate(moves, start=1):
            yield render_line(self._move_to_line(mv, cuo=cuo, balances=balances))

    def generate_to_file(self, fobj) -> int:
        count = 0
        for txt in self.iter_lines():
            fobj.write((txt + "\r\n").encode("utf-8"))
            count += 1
        return count

    def _move_to_line(self, mv, *, cuo: int, balances: dict) -> Ple12_1Line:
        is_in = mv.location_dest_id.usage == "internal" and mv.location_id.usage != "internal"
        is_out = mv.location_id.usage == "internal" and mv.location_dest_id.usage != "internal"
        qty = Decimal(str(mv.product_uom_qty or 0))
        entry = qty if is_in else Decimal("0")
        exit_ = qty if is_out else Decimal("0")
        pid = mv.product_id.id
        new_balance = balances.get(pid, Decimal("0")) + entry - exit_
        balances[pid] = new_balance
        return Ple12_1Line(
            period=self.period,
            cuo=cuo,
            correlativo=f"S{mv.id:08d}",
            op_type=self._infer_op_type(mv, is_in=is_in, is_out=is_out),
            op_date=mv.date.date() if hasattr(mv.date, "date") else mv.date,
            product_code=(mv.product_id.default_code or f"P{mv.product_id.id}").strip(),
            product_name=mv.product_id.name or "",
            unit_code="NIU",
            entry_qty=entry,
            exit_qty=exit_,
            balance_qty=new_balance,
            state="1",
        )

    @staticmethod
    def _infer_op_type(mv, *, is_in: bool, is_out: bool) -> str:
        ptype = (mv.picking_id.picking_type_id.code or "") if mv.picking_id else ""
        if ptype == "incoming":
            return OP_COMPRA
        if ptype == "outgoing":
            return OP_VENTA
        if ptype == "internal":
            return OP_TRANSFER_INTERNA
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


def _fmt_date(d) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _clean(s: str) -> str:
    if not s:
        return ""
    return s.replace("|", " ").strip()
