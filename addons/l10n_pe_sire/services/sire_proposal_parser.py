# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Parser de TXT de propuesta RCE (Compras) descargado de SIRE.

Estructura SUNAT (separador '|', terminando con '|'):
  1.  Período (YYYYMM)
  2.  CUO
  3.  Correlativo del comprobante
  4.  Tipo de comprobante (cat 10: 01 Factura, 07 NC, 08 ND, ...)
  5.  Serie
  6.  Número
  7.  Fecha emisión (DD/MM/YYYY)
  8.  Fecha vencimiento (DD/MM/YYYY o vacío)
  9.  Tipo doc identidad proveedor (cat 06)
  10. Número doc identidad proveedor
  11. Apellidos/Razón social proveedor
  12. Base imponible gravada (decimal)
  13. IGV (decimal)
  14. Base no gravada (decimal)
  15. ISC
  16. Total
  17. Tipo de cambio
  ... (+ campos finales que aquí ignoramos)

Solo necesitamos lo justo para hacer match contra account.move.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass
class RceProposalLine:
    period: str  # 'YYYYMM'
    cuo: str
    doc_type_code: str
    serie: str
    number: str
    issue_date: date | None
    due_date: date | None
    supplier_doc_type: str
    supplier_doc_number: str
    supplier_name: str
    base_taxable: Decimal
    igv: Decimal
    base_untaxed: Decimal
    isc: Decimal
    total: Decimal


def parse_rce_txt(content: bytes, encoding: str = "utf-8") -> list[RceProposalLine]:
    """Parsea el TXT bytes → lista RceProposalLine. Ignora líneas vacías."""
    text = content.decode(encoding, errors="replace")
    # SUNAT usa CRLF pero soportamos LF también
    lines = [ln for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    out = []
    for ln in lines:
        try:
            out.append(_parse_one(ln))
        except Exception:
            # Línea defectuosa: la saltamos. El conciliador hará best-effort.
            continue
    return out


def _parse_one(line: str) -> RceProposalLine:
    cols = line.split("|")
    # Necesitamos al menos hasta col 16 (total). Si hay menos, no es válida.
    if len(cols) < 17:
        raise ValueError(f"línea corta ({len(cols)} cols): {line[:80]}")
    return RceProposalLine(
        period=_strip(cols[0]),
        cuo=_strip(cols[1]),
        doc_type_code=_strip(cols[3]),
        serie=_strip(cols[4]),
        number=_strip(cols[5]),
        issue_date=_parse_date(cols[6]),
        due_date=_parse_date(cols[7]),
        supplier_doc_type=_strip(cols[8]),
        supplier_doc_number=_strip(cols[9]),
        supplier_name=_strip(cols[10]),
        base_taxable=_parse_amt(cols[11]),
        igv=_parse_amt(cols[12]),
        base_untaxed=_parse_amt(cols[13]),
        isc=_parse_amt(cols[14]),
        total=_parse_amt(cols[15]),
    )


def _strip(s: str) -> str:
    return (s or "").strip()


def _parse_date(s: str) -> date | None:
    s = _strip(s)
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amt(s: str) -> Decimal:
    s = _strip(s)
    if not s:
        return Decimal("0")
    # SUNAT a veces usa coma decimal; lo soportamos
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")
