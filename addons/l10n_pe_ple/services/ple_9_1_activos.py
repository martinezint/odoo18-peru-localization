# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador PLE 9.1 — Registro de Activos Fijos.

Libro ANUAL. Una línea TXT por activo fijo del ejercicio.

Dependencia suave: requiere el modelo `account.asset` (OCA
`account_asset_management` o Odoo Enterprise `account_asset`).
Si no existe el modelo, el generador devuelve 0 líneas y el wizard
lo indica al usuario.

Estructura SUNAT Anexo 9.1 (versión esencial, 18 columnas):
  1.  Período (YYYY1200, anual)
  2.  CUO
  3.  Correlativo
  4.  Cuenta contable activo
  5.  Código del activo (interno)
  6.  Descripción
  7.  Marca
  8.  Modelo
  9.  Número de serie / placa
 10. Fecha de adquisición (DD/MM/YYYY)
 11. Fecha de inicio del uso
 12. Método de depreciación (Cat 25)
 13. Vida útil (años)
 14. Tasa de depreciación (%)
 15. Valor histórico
 16. Depreciación acumulada (ejercicios anteriores)
 17. Depreciación del ejercicio
 18. Depreciación acumulada al cierre
 19. Estado: '1' inicial, '8' ajuste, '9' anulado

Para empresa SIN OCA asset_management: este libro queda vacío (el
contador debe llevarlo manualmente fuera de Odoo).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PLE_ACTIVOS_COLUMNS = 19


@dataclass
class Ple9_1Line:
    period: str
    cuo: int
    correlativo: str
    account_code: str
    asset_code: str
    asset_name: str
    brand: str = ""
    model: str = ""
    serial: str = ""
    acquisition_date: date | None = None
    start_date: date | None = None
    method_code: str = "01"  # Cat 25
    useful_life_years: int = 0
    depreciation_rate: Decimal = Decimal("0")
    historical_value: Decimal = Decimal("0")
    accumulated_prev: Decimal = Decimal("0")
    depreciation_year: Decimal = Decimal("0")
    accumulated_close: Decimal = Decimal("0")
    state: str = "1"


def render_line(line: Ple9_1Line) -> str:
    cols = [
        line.period,
        str(line.cuo),
        line.correlativo,
        line.account_code,
        line.asset_code,
        _clean(line.asset_name),
        _clean(line.brand),
        _clean(line.model),
        _clean(line.serial),
        _fmt_date(line.acquisition_date),
        _fmt_date(line.start_date),
        line.method_code,
        str(line.useful_life_years),
        _fmt_pct(line.depreciation_rate),
        _fmt_amt(line.historical_value),
        _fmt_amt(line.accumulated_prev),
        _fmt_amt(line.depreciation_year),
        _fmt_amt(line.accumulated_close),
        line.state,
    ]
    return "|".join(cols) + "|"


class Ple9_1Generator:
    """Itera líneas TXT del Registro de Activos Fijos.

    Si `account.asset` no está instalado, devuelve un iterador vacío
    (no rompe — solo no emite líneas).
    """

    def __init__(self, env, company, period_yyyymm: str):
        self.env = env
        self.company = company
        self.year = int(period_yyyymm[:4])
        self.period = f"{self.year}1200"  # anual

    def iter_lines(self) -> Iterator[str]:
        Asset = self.env.get("account.asset")
        if Asset is None:
            return  # OCA/EE asset model no instalado
        date_to = date(self.year + 1, 1, 1)
        # Filtros: activos creados/activos en el ejercicio
        assets = Asset.search(
            [
                ("company_id", "=", self.company.id),
                ("state", "in", ("open", "running", "close")),
                ("date_start", "<", date_to),
            ],
            order="id",
        )
        for cuo, asset in enumerate(assets, start=1):
            yield render_line(self._asset_to_line(asset, cuo=cuo))

    def generate_to_file(self, fobj) -> int:
        count = 0
        for txt in self.iter_lines():
            fobj.write((txt + "\r\n").encode("utf-8"))
            count += 1
        return count

    def _asset_to_line(self, asset, *, cuo: int) -> Ple9_1Line:
        """Lectura defensiva de campos del modelo (variaciones OCA/EE)."""

        def _g(record, *names, default=None):
            for n in names:
                if hasattr(record, n):
                    val = getattr(record, n)
                    if val is not None and val is not False:
                        return val
            return default

        return Ple9_1Line(
            period=self.period,
            cuo=cuo,
            correlativo=f"A{asset.id:08d}",
            account_code=(_g(asset, "account_asset_id", default=False).code or "")
            if _g(asset, "account_asset_id", default=False)
            else "",
            asset_code=_g(asset, "code", "default_code", default=f"AF{asset.id}"),
            asset_name=_g(asset, "name", default=""),
            acquisition_date=_g(asset, "purchase_date", "date", default=None),
            start_date=_g(asset, "date_start", "first_depreciation_date", default=None),
            useful_life_years=int(_g(asset, "method_number", "useful_life", default=0) or 0),
            historical_value=Decimal(str(_g(asset, "purchase_value", "value", default=0) or 0)),
            accumulated_prev=Decimal(
                str(_g(asset, "value_depreciated", "depreciated_value", default=0) or 0)
            ),
            depreciation_year=Decimal("0"),  # cálculo per-ejercicio requiere logic adicional
            accumulated_close=Decimal(
                str(_g(asset, "value_depreciated", "depreciated_value", default=0) or 0)
            ),
            state="1",
        )


def _fmt_amt(value, decimals: int = 2) -> str:
    if value is None:
        return f"{Decimal('0'):.{decimals}f}"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.{decimals}f}"


def _fmt_pct(value) -> str:
    return _fmt_amt(value, decimals=2)


def _fmt_date(d) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _clean(s) -> str:
    if not s:
        return ""
    return str(s).replace("|", " ").strip()
