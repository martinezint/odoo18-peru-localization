# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador PLE 8.1 — Registro de Compras.

Estructura similar a 14.1 pero con columnas adicionales para crédito fiscal,
retenciones, sustento, etc. Total ~52 columnas en v5.x.

v1 implementa los campos más usados; deja en vacío los condicionales.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from .ple_14_1_ventas import _clean_text, _fmt_amt, _fmt_date


PLE_COMPRAS_COLUMNS = 52


@dataclass
class Ple8_1Line:
    """Línea Registro de Compras 8.1."""
    period: str
    cuo: int
    correlativo: str
    issue_date: date
    due_date: Optional[date] = None     # fecha vencimiento O fecha pago retención
    doc_type: str = "01"
    serie: str = ""
    issue_year: str = ""
    initial_number: str = ""            # rango: número desde
    final_number: str = ""              # rango: número hasta
    supplier_id_type: str = "6"
    supplier_id: str = ""
    supplier_name: str = ""

    taxed_base_other_uses: Decimal = Decimal("0.00")  # base gravada destinada a otros usos
    igv_other_uses: Decimal = Decimal("0.00")
    taxed_base_export: Decimal = Decimal("0.00")
    igv_export: Decimal = Decimal("0.00")
    taxed_base_no_export: Decimal = Decimal("0.00")    # común
    igv_no_export: Decimal = Decimal("0.00")
    taxed_base_no_credit: Decimal = Decimal("0.00")
    igv_no_credit: Decimal = Decimal("0.00")
    exonerated_amount: Decimal = Decimal("0.00")
    unaffected_amount: Decimal = Decimal("0.00")
    isc: Decimal = Decimal("0.00")
    other_charges: Decimal = Decimal("0.00")
    icbper: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    currency: str = "PEN"
    exchange_rate: Decimal = Decimal("1.000")

    ref_issue_date: Optional[date] = None
    ref_doc_type: str = ""
    ref_serie: str = ""
    ref_number: str = ""

    detraccion_date: Optional[date] = None
    detraccion_number: str = ""

    foreign_doc_type: str = ""          # solo para no domiciliados
    foreign_doc_number: str = ""
    foreign_doc_date: Optional[date] = None

    state: str = "1"


def render_line(line: Ple8_1Line) -> str:
    cols = [
        line.period,
        str(line.cuo),
        line.correlativo,
        _fmt_date(line.issue_date),
        _fmt_date(line.due_date),
        line.doc_type,
        line.serie,
        line.issue_year,
        line.initial_number,
        line.final_number,
        line.supplier_id_type,
        line.supplier_id,
        _clean_text(line.supplier_name),
        _fmt_amt(line.taxed_base_other_uses),
        _fmt_amt(line.igv_other_uses),
        _fmt_amt(line.taxed_base_export),
        _fmt_amt(line.igv_export),
        _fmt_amt(line.taxed_base_no_export),
        _fmt_amt(line.igv_no_export),
        _fmt_amt(line.taxed_base_no_credit),
        _fmt_amt(line.igv_no_credit),
        _fmt_amt(line.exonerated_amount),
        _fmt_amt(line.unaffected_amount),
        _fmt_amt(line.isc),
        _fmt_amt(line.other_charges),
        _fmt_amt(line.icbper),
        _fmt_amt(line.total),
        line.currency,
        _fmt_amt(line.exchange_rate, decimals=3),
        _fmt_date(line.ref_issue_date),
        line.ref_doc_type,
        line.ref_serie,
        line.ref_number,
        _fmt_date(line.detraccion_date),
        line.detraccion_number,
        line.foreign_doc_type,
        line.foreign_doc_number,
        _fmt_date(line.foreign_doc_date),
        line.state,
    ]
    while len(cols) < PLE_COMPRAS_COLUMNS:
        cols.append("")
    return "|".join(cols) + "|"


class Ple8_1Generator:
    """Genera PLE 8.1 desde account.move (in_invoice, in_refund)."""

    def __init__(self, env, company, period_yyyymm: str):
        self.env = env
        self.company = company
        self.period = f"{period_yyyymm}00"
        self.period_yyyymm = period_yyyymm

    def iter_lines(self) -> Iterator[str]:
        Move = self.env["account.move"]
        year = int(self.period_yyyymm[:4])
        month = int(self.period_yyyymm[4:])
        date_from = date(year, month, 1)
        date_to = date(year + (1 if month == 12 else 0),
                       1 if month == 12 else month + 1, 1)

        domain = [
            ("company_id", "=", self.company.id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<", date_to),
        ]
        moves = Move.search(domain, order="date, id")
        for i, move in enumerate(moves, start=1):
            yield render_line(self._move_to_line(move, cuo=i))

    def generate_to_file(self, fobj) -> int:
        count = 0
        for txt in self.iter_lines():
            fobj.write((txt + "\r\n").encode("utf-8"))
            count += 1
        return count

    def _move_to_line(self, move, *, cuo: int) -> Ple8_1Line:
        serie, number = self._split_move_name(move.ref or move.name or "")
        supplier = move.partner_id

        doc_type = "07" if move.move_type == "in_refund" else "01"
        sup_id_type = "6"
        if supplier.l10n_latam_identification_type_id and \
                supplier.l10n_latam_identification_type_id.l10n_pe_vat_code:
            sup_id_type = supplier.l10n_latam_identification_type_id.l10n_pe_vat_code

        total = Decimal(str(move.amount_total or 0))
        igv = Decimal(str(move.amount_tax or 0))
        taxed_base = Decimal(str(move.amount_untaxed or 0))

        return Ple8_1Line(
            period=self.period,
            cuo=cuo,
            correlativo=f"M{move.id:08d}",
            issue_date=move.invoice_date or move.date,
            due_date=move.invoice_date_due,
            doc_type=doc_type,
            serie=serie,
            initial_number=number,
            final_number=number,
            supplier_id_type=sup_id_type,
            supplier_id=(supplier.vat or "").strip(),
            supplier_name=supplier.name or "",
            taxed_base_no_export=taxed_base,
            igv_no_export=igv,
            total=total,
            currency=move.currency_id.name or "PEN",
            state="1",
        )

    @staticmethod
    def _split_move_name(name: str) -> tuple[str, str]:
        if not name:
            return ("", "")
        for sep in ("/", "-"):
            if sep in name:
                parts = name.split(sep, 1)
                return (parts[0], parts[1])
        return (name, "")
