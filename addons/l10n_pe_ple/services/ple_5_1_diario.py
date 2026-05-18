# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador PLE 5.1 — Libro Diario.

Una línea TXT por cada `account.move.line` de movimientos posteados del
período. Columnas según Anexo 5.1 R.S. 286-2009 (vigente PLE 5.x):

  1. Período (YYYYMM00)
  2. CUO (Código Único de Operación, secuencial dentro del archivo)
  3. Correlativo del asiento o código único (string)
  4. Código de la cuenta contable (PCGE 4-7 dígitos)
  5. Unidad operativa (opcional)
  6. Centro de costo (opcional)
  7. Tipo de moneda (PEN/USD según ISO 4217)
  8. Tipo de tabla — '0' por defecto
  9. Código analítica (3 dígitos, opcional)
 10. Tipo de comprobante (cat 1; 00 si no aplica)
 11. Número serie del comprobante
 12. Año emisión (4 dígitos, solo tickets máquina)
 13. Número del comprobante
 14. Fecha contable (DD/MM/YYYY)
 15. Fecha vencimiento
 16. Glosa principal del asiento
 17. Glosa de referencia
 18. Debe (2 decimales)
 19. Haber (2 decimales)
 20. Estado: '1' inicial, '8' ajuste posterior, '9' anulado

Total: 32 columnas separadas por '|', terminando con '|'.
Encoding UTF-8, line endings CRLF.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PLE_DIARIO_COLUMNS = 32


@dataclass
class Ple5_1Line:
    period: str
    cuo: int
    correlativo: str
    account_code: str
    currency: str = "PEN"
    doc_type: str = "00"
    serie: str = ""
    issue_year: str = ""
    number: str = ""
    accounting_date: date | None = None
    due_date: date | None = None
    glosa: str = ""
    ref_glosa: str = ""
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    state: str = "1"
    unidad_operativa: str = ""
    centro_costo: str = ""
    analitica: str = ""
    tipo_tabla: str = "0"


def render_line(line: Ple5_1Line) -> str:
    cols = [
        line.period,
        str(line.cuo),
        line.correlativo,
        line.account_code,
        line.unidad_operativa,
        line.centro_costo,
        line.currency,
        line.tipo_tabla,
        line.analitica,
        line.doc_type,
        line.serie,
        line.issue_year,
        line.number,
        _fmt_date(line.accounting_date),
        _fmt_date(line.due_date),
        _clean(line.glosa),
        _clean(line.ref_glosa),
        _fmt_amt(line.debit),
        _fmt_amt(line.credit),
        line.state,
    ]
    while len(cols) < PLE_DIARIO_COLUMNS:
        cols.append("")
    return "|".join(cols) + "|"


class Ple5_1Generator:
    """Itera líneas TXT del Libro Diario desde account.move.line posteados."""

    def __init__(self, env, company, period_yyyymm: str):
        self.env = env
        self.company = company
        self.period = f"{period_yyyymm}00"
        self.period_yyyymm = period_yyyymm

    def iter_lines(self) -> Iterator[str]:
        Line = self.env["account.move.line"]
        year = int(self.period_yyyymm[:4])
        month = int(self.period_yyyymm[4:])
        date_from = date(year, month, 1)
        date_to = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        domain = [
            ("company_id", "=", self.company.id),
            ("parent_state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<", date_to),
        ]
        lines = Line.search(domain, order="move_id, id")
        for cuo, ml in enumerate(lines, start=1):
            yield render_line(self._aml_to_line(ml, cuo=cuo))

    def generate_to_file(self, fobj) -> int:
        count = 0
        for txt in self.iter_lines():
            fobj.write((txt + "\r\n").encode("utf-8"))
            count += 1
        return count

    def _aml_to_line(self, ml, *, cuo: int) -> Ple5_1Line:
        move = ml.move_id
        serie, number = self._split_move_name(move.name or "")
        doc_type = self._infer_doc_type(move)
        return Ple5_1Line(
            period=self.period,
            cuo=cuo,
            correlativo=f"M{move.id:08d}",
            account_code=(ml.account_id.code or "").strip(),
            currency=ml.currency_id.name or move.currency_id.name or "PEN",
            doc_type=doc_type,
            serie=serie,
            number=number,
            accounting_date=ml.date,
            due_date=move.invoice_date_due,
            glosa=(move.ref or ml.name or "")[:200],
            ref_glosa="",
            debit=Decimal(str(ml.debit or 0)),
            credit=Decimal(str(ml.credit or 0)),
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

    @staticmethod
    def _infer_doc_type(move) -> str:
        """SUNAT cat 01 desde el move. '00' si no es comprobante factura/boleta."""
        if move.move_type == "out_invoice":
            return "01"
        if move.move_type == "out_refund":
            return "07"
        if move.move_type == "in_invoice":
            return "01"
        if move.move_type == "in_refund":
            return "07"
        # entry / asiento manual
        return "00"


def _fmt_amt(value, decimals: int = 2) -> str:
    if value is None:
        return f"{Decimal('0'):.{decimals}f}"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.{decimals}f}"


def _fmt_date(d):
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _clean(s: str) -> str:
    if not s:
        return ""
    return s.replace("|", " ").strip()
