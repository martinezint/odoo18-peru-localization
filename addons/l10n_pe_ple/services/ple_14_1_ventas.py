# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador PLE 14.1 — Registro de Ventas e Ingresos.

Estructura de cada línea (pipe-separada). Columnas según
Anexo 4.1 RS 286-2009 actualizado (v5.x):

  1. Período (YYYYMM00)
  2. CUO (Código Único de Operación, secuencial dentro del archivo)
  3. Correlativo del Registro o Código Único de la Operación (M<id>)
  4. Fecha de emisión del comprobante (DD/MM/YYYY)
  5. Fecha de vencimiento (DD/MM/YYYY o vacío)
  6. Tipo de comprobante (cat 10; 01 Factura, 03 Boleta, 07 NC, 08 ND)
  7. Serie
  8. Año de emisión (4 dígitos) — sólo para tickets de máquina registradora
  9. Número del comprobante
 10. Tipo doc identidad del cliente (cat 6: 1 DNI, 6 RUC, 4 CE, ...)
 11. Número doc identidad cliente
 12. Apellidos y nombres / razón social
 13. Valor facturado exportación
 14. Base imponible operación gravada
 15. ICBPER
 16. IGV / IPM
 17. Importe operación exonerada
 18. Importe operación inafecta
 19. ISC
 20. ICBPER (otro)  — algunos formularios duplican
 21. Otros tributos / Cargos
 22. Importe total
 23. Código moneda (cat 2)
 24. Tipo de cambio
 25. Fecha emisión doc original (NC/ND)
 26. Tipo doc original (cat 10)
 27. Serie doc original
 28. Año doc original
 29. Número doc original
 30. Identificador del bien o servicio
 31. Erróneo / referencia / serie máquina registradora
 32. Estado: '1' inicial; '8' incluido tarde; '9' anulado
 33-46 ... varios (proyectos, declaraciones, etc.) — la mayoría se dejan vacíos
     en v1; SUNAT acepta así si la columna 32 indica que no aplica.

Total: 46 columnas separadas por '|'. La línea TERMINA con '|' después de la
última columna. Sin BOM. Encoding: ISO-8859-1 (latin1) o UTF-8 — SUNAT acepta
ambos en PLE 5.x; usamos UTF-8.

Salida: generador (yield string por línea). El caller decide si va a archivo
en disco (streaming) o a BytesIO en memoria.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PLE_VENTAS_COLUMNS = 46  # número total de columnas en la línea


@dataclass
class Ple14_1Line:
    """Una línea del Registro de Ventas 14.1.

    No todos los campos son requeridos. Los Decimal por defecto = 0.00.
    """

    period: str  # 'YYYYMM00'
    cuo: int  # secuencial 1, 2, 3...
    correlativo: str  # 'M' + serie + número, ej. 'MF001-1'
    issue_date: date
    due_date: date | None = None
    doc_type: str = "01"  # cat 10
    serie: str = ""
    issue_year: str = ""  # solo para ticket máquina
    number: str = ""  # número del comprobante (sin serie)
    customer_id_type: str = "6"  # cat 6
    customer_id: str = ""
    customer_name: str = ""
    export_value: Decimal = Decimal("0.00")
    taxed_base: Decimal = Decimal("0.00")
    icbper: Decimal = Decimal("0.00")
    igv: Decimal = Decimal("0.00")
    exonerated_amount: Decimal = Decimal("0.00")
    unaffected_amount: Decimal = Decimal("0.00")
    isc: Decimal = Decimal("0.00")
    icbper_2: Decimal = Decimal("0.00")
    other_charges: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    currency: str = "PEN"
    exchange_rate: Decimal = Decimal("1.000")
    ref_issue_date: date | None = None
    ref_doc_type: str = ""
    ref_serie: str = ""
    ref_issue_year: str = ""
    ref_number: str = ""
    ident_bien_servicio: str = ""
    erroneous_ref: str = ""
    state: str = "1"  # 1 inicial, 8 incluido tarde, 9 anulado


def render_line(line: Ple14_1Line) -> str:
    """Convierte un Ple14_1Line en una línea de texto pipe-separada.

    SUNAT exige terminar con '|' después de la última columna y newline LF.
    """
    cols = [
        line.period,
        str(line.cuo),
        line.correlativo,
        _fmt_date(line.issue_date),
        _fmt_date(line.due_date),
        line.doc_type,
        line.serie,
        line.issue_year,
        line.number,
        line.customer_id_type,
        line.customer_id,
        _clean_text(line.customer_name),
        _fmt_amt(line.export_value),
        _fmt_amt(line.taxed_base),
        _fmt_amt(line.icbper),
        _fmt_amt(line.igv),
        _fmt_amt(line.exonerated_amount),
        _fmt_amt(line.unaffected_amount),
        _fmt_amt(line.isc),
        _fmt_amt(line.icbper_2),
        _fmt_amt(line.other_charges),
        _fmt_amt(line.total),
        line.currency,
        _fmt_amt(line.exchange_rate, decimals=3),
        _fmt_date(line.ref_issue_date),
        line.ref_doc_type,
        line.ref_serie,
        line.ref_issue_year,
        line.ref_number,
        line.ident_bien_servicio,
        line.erroneous_ref,
        line.state,
    ]
    # Rellena con vacíos hasta llegar a 46 columnas (los proyectos/declaraciones)
    while len(cols) < PLE_VENTAS_COLUMNS:
        cols.append("")
    # SUNAT exige terminar con '|' adicional → join + '|' + newline implícito
    return "|".join(cols) + "|"


class Ple14_1Generator:
    """Genera el PLE 14.1 desde un set de account.move (out_invoice, out_refund).

    Usa el ORM de Odoo. Streaming: produce líneas una a una (Iterator) para no
    materializar todo en memoria para BDs grandes.
    """

    def __init__(self, env, company, period_yyyymm: str):
        self.env = env
        self.company = company
        self.period = f"{period_yyyymm}00"
        self.period_yyyymm = period_yyyymm

    def iter_lines(self) -> Iterator[str]:
        """Itera líneas TXT desde account.move posteados del período."""
        Move = self.env["account.move"]
        # account.move.date queda en el período; movimientos out_* posteados.
        year = int(self.period_yyyymm[:4])
        month = int(self.period_yyyymm[4:])
        date_from = date(year, month, 1)
        if month == 12:
            date_to = date(year + 1, 1, 1)
        else:
            date_to = date(year, month + 1, 1)

        domain = [
            ("company_id", "=", self.company.id),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<", date_to),
        ]
        moves = Move.search(domain, order="date, id")
        for i, move in enumerate(moves, start=1):
            line = self._move_to_line(move, cuo=i)
            yield render_line(line)

    def generate_to_file(self, fobj) -> int:
        """Escribe todas las líneas a un file-like (BytesIO o file). Devuelve count."""
        count = 0
        for txt in self.iter_lines():
            fobj.write((txt + "\r\n").encode("utf-8"))
            count += 1
        return count

    # ─── Mapping account.move → Ple14_1Line ──────────────────────

    def _move_to_line(self, move, *, cuo: int) -> Ple14_1Line:
        serie, number = self._split_move_name(move.name or "")
        partner = move.partner_id
        # Tipo de comprobante SUNAT: del l10n_latam_document_type_id si está,
        # fallback a '01' para facturas y '07' para refunds.
        doc_type = self._infer_doc_type(move)
        # Customer id type: del l10n_latam_identification_type_id.l10n_pe_vat_code
        cust_id_type = "6"
        if (
            partner.l10n_latam_identification_type_id
            and partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        ):
            cust_id_type = partner.l10n_latam_identification_type_id.l10n_pe_vat_code

        # Importes — extraemos lo más limpio posible del move
        total = Decimal(str(move.amount_total or 0))
        igv = Decimal(str(move.amount_tax or 0))
        taxed_base = Decimal(str(move.amount_untaxed or 0))

        return Ple14_1Line(
            period=self.period,
            cuo=cuo,
            correlativo=f"M{move.id:08d}",
            issue_date=move.invoice_date or move.date,
            due_date=move.invoice_date_due,
            doc_type=doc_type,
            serie=serie,
            number=number,
            customer_id_type=cust_id_type,
            customer_id=(partner.vat or "").strip(),
            customer_name=partner.name or "",
            taxed_base=taxed_base,
            igv=igv,
            total=total,
            currency=move.currency_id.name or "PEN",
            state="1",
        )

    @staticmethod
    def _split_move_name(name: str) -> tuple[str, str]:
        """'F001/00000123' o 'F001-123' → ('F001', '00000123' o '123')."""
        if not name:
            return ("", "")
        for sep in ("/", "-"):
            if sep in name:
                parts = name.split(sep, 1)
                return (parts[0], parts[1])
        return (name, "")

    @staticmethod
    def _infer_doc_type(move) -> str:
        """SUNAT cat 10 desde el move. Por defecto 01 Factura, 07 NC."""
        if move.move_type == "out_refund":
            return "07"
        # Si el partner tiene identificación tipo DNI (1) → posible boleta (03)
        # pero como heurística simple, todo out_invoice → 01.
        return "01"


def _fmt_amt(value, decimals: int = 2) -> str:
    """Formato SUNAT: punto decimal, sin separador de miles, decimales fijos."""
    if value is None:
        return f"{Decimal('0'):.{decimals}f}"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.{decimals}f}"


def _fmt_date(d: date | None) -> str:
    """SUNAT exige DD/MM/YYYY."""
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _clean_text(s: str) -> str:
    """SUNAT prohíbe pipe '|' dentro de campos de texto."""
    if not s:
        return ""
    return s.replace("|", " ").strip()
