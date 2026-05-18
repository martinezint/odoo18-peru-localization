# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador PLE 3.1 — Libro de Inventarios y Balances (Balance General).

Libro anual. Una línea TXT por cuenta de balance (clases 1-5 del PCGE)
con sus saldos al cierre del ejercicio.

Estructura SUNAT Anexo 3.1:
  1. Período (YYYY0000 anual, cierre 31/12)
  2. CUO
  3. Correlativo
  4. Código de cuenta contable
  5. Denominación cuenta
  6. Saldo deudor (2 decimales)
  7. Saldo acreedor (2 decimales)
  8. Estado: '1' inicial, '8' ajuste posterior, '9' anulado

Total: 8 columnas separadas por '|', terminando con '|'.
Solo cuentas de balance (códigos PCGE clase 1-5: Activo y Pasivo).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PLE_INVENTARIO_COLUMNS = 8

# PCGE clases de balance: Activos (1, 2, 3) + Pasivos (4) + Patrimonio (5)
BALANCE_CLASSES = ("1", "2", "3", "4", "5")


@dataclass
class Ple3_1Line:
    period: str
    cuo: int
    correlativo: str
    account_code: str
    account_name: str = ""
    debit_balance: Decimal = Decimal("0.00")
    credit_balance: Decimal = Decimal("0.00")
    state: str = "1"


def render_line(line: Ple3_1Line) -> str:
    cols = [
        line.period,
        str(line.cuo),
        line.correlativo,
        line.account_code,
        _clean(line.account_name),
        _fmt_amt(line.debit_balance),
        _fmt_amt(line.credit_balance),
        line.state,
    ]
    return "|".join(cols) + "|"


class Ple3_1Generator:
    """Itera líneas TXT del libro Inventarios y Balances anual."""

    def __init__(self, env, company, period_yyyymm: str):
        """period_yyyymm: para 3.1 lo usamos para extraer el AÑO. El period
        del archivo será siempre YYYY0000 (anual)."""
        self.env = env
        self.company = company
        self.year = int(period_yyyymm[:4])
        self.period = f"{self.year}0000"

    def iter_lines(self) -> Iterator[str]:
        rows = self._aggregate_balance_accounts()
        for cuo, row in enumerate(rows, start=1):
            yield render_line(
                Ple3_1Line(
                    period=self.period,
                    cuo=cuo,
                    correlativo=f"B{cuo:08d}",
                    account_code=row["code"],
                    account_name=row["name"],
                    debit_balance=Decimal(str(row["debit_balance"])),
                    credit_balance=Decimal(str(row["credit_balance"])),
                    state="1",
                )
            )

    def generate_to_file(self, fobj) -> int:
        count = 0
        for txt in self.iter_lines():
            fobj.write((txt + "\r\n").encode("utf-8"))
            count += 1
        return count

    def _aggregate_balance_accounts(self) -> list[dict]:
        """Saldo deudor/acreedor de cuentas clases 1-5 al cierre del ejercicio."""
        date_to = date(self.year + 1, 1, 1)
        Move = self.env["account.move"]
        moves = Move.search(
            [
                ("company_id", "=", self.company.id),
                ("state", "=", "posted"),
                ("date", "<", date_to),
            ]
        )
        Line = self.env["account.move.line"]
        groups = Line.read_group(
            domain=[("move_id", "in", moves.ids)],
            fields=["debit:sum", "credit:sum"],
            groupby=["account_id"],
        )
        out = []
        for g in groups:
            debit = g["debit"] or 0.0
            credit = g["credit"] or 0.0
            account_id = g["account_id"][0]
            account = self.env["account.account"].browse(account_id)
            code = (account.code or "").strip()
            # Solo cuentas de balance (clase 1-5 PCGE)
            if not code or code[0] not in BALANCE_CLASSES:
                continue
            # Saldo neto: deudor si debit>credit, acreedor si credit>debit
            net = debit - credit
            debit_bal = net if net > 0 else 0.0
            credit_bal = -net if net < 0 else 0.0
            if debit_bal == 0 and credit_bal == 0:
                continue
            out.append(
                {
                    "account_id": account_id,
                    "code": code,
                    "name": account.name or "",
                    "debit_balance": debit_bal,
                    "credit_balance": credit_bal,
                }
            )
        out.sort(key=lambda r: r["code"])
        return out


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
