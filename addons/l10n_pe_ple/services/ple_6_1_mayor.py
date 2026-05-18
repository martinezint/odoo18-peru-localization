# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador PLE 6.1 — Libro Mayor.

Una línea TXT por cuenta contable con movimientos posteados en el período.
A diferencia del Diario (5.1) que detalla cada `account.move.line`, el Mayor
agrega por cuenta: SUM(debit), SUM(credit) GROUP BY account_id.

Estructura SUNAT Anexo 6.1 (R.S. 286-2009 y modificatorias):

  1. Período (YYYYMM00)
  2. CUO (Código Único de Operación, secuencial dentro del archivo)
  3. Correlativo del asiento o código único (string)
  4. Código de la cuenta contable (PCGE)
  5. Glosa o denominación de la cuenta
  6. Saldos y movimientos — debe (2 decimales)
  7. Saldos y movimientos — haber (2 decimales)
  8. Estado: '1' inicial, '8' ajuste posterior, '9' anulado

Total: 8 columnas separadas por '|', terminando con '|'.
Encoding UTF-8, line endings CRLF.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

PLE_MAYOR_COLUMNS = 8


@dataclass
class Ple6_1Line:
    period: str
    cuo: int
    correlativo: str
    account_code: str
    account_name: str = ""
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    state: str = "1"


def render_line(line: Ple6_1Line) -> str:
    cols = [
        line.period,
        str(line.cuo),
        line.correlativo,
        line.account_code,
        _clean(line.account_name),
        _fmt_amt(line.debit),
        _fmt_amt(line.credit),
        line.state,
    ]
    return "|".join(cols) + "|"


class Ple6_1Generator:
    """Itera líneas TXT del Libro Mayor agregando AML posteados por cuenta."""

    def __init__(self, env, company, period_yyyymm: str):
        self.env = env
        self.company = company
        self.period = f"{period_yyyymm}00"
        self.period_yyyymm = period_yyyymm

    def iter_lines(self) -> Iterator[str]:
        rows = self._aggregate_by_account()
        for cuo, row in enumerate(rows, start=1):
            yield render_line(
                Ple6_1Line(
                    period=self.period,
                    cuo=cuo,
                    correlativo=f"M{cuo:08d}",
                    account_code=row["code"],
                    account_name=row["name"],
                    debit=Decimal(str(row["debit"])),
                    credit=Decimal(str(row["credit"])),
                    state="1",
                )
            )

    def generate_to_file(self, fobj) -> int:
        count = 0
        for txt in self.iter_lines():
            fobj.write((txt + "\r\n").encode("utf-8"))
            count += 1
        return count

    def _aggregate_by_account(self) -> list[dict]:
        """SUM(debit), SUM(credit) GROUP BY account agrupando AML del período."""
        year = int(self.period_yyyymm[:4])
        month = int(self.period_yyyymm[4:])
        from datetime import date

        date_from = date(year, month, 1)
        date_to = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        self.env.cr.execute(
            """
            SELECT
                aa.id        AS account_id,
                aa.code      AS code,
                aa.name      AS name,
                SUM(aml.debit)  AS debit,
                SUM(aml.credit) AS credit
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %s
              AND aml.parent_state = 'posted'
              AND aml.date >= %s
              AND aml.date <  %s
            GROUP BY aa.id, aa.code, aa.name
            HAVING SUM(aml.debit) <> 0 OR SUM(aml.credit) <> 0
            ORDER BY aa.code
            """,
            (self.company.id, date_from, date_to),
        )
        cols = [d.name for d in self.env.cr.description]
        return [dict(zip(cols, row, strict=False)) for row in self.env.cr.fetchall()]


def _fmt_amt(value, decimals: int = 2) -> str:
    if value is None:
        return f"{Decimal('0'):.{decimals}f}"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.{decimals}f}"


def _clean(s: str) -> str:
    if not s:
        return ""
    return s.replace("|", " ").strip()
