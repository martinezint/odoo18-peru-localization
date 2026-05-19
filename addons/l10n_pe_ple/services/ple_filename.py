# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Utilidad para construir el nombre estándar SUNAT de un archivo PLE.

Formato (Manual del Programador PLE v5.x, Resolución SUNAT 286-2009 y modif.):

    LE<RUC><AÑO><MES><DIA><LIBRO><OPER><INDOPS><MONEDA><MIX>.txt

Componentes:
- LE         : prefijo literal (2 chars).
- RUC        : 11 dígitos del contribuyente emisor.
- AÑO MES DIA: 8 dígitos YYYYMMDD. Para libros mensuales: YYYYMM00.
              Para libros anuales: YYYY1200.
- LIBRO      : 5-6 dígitos identificando el libro/sub-libro.
              14.1 Registro Ventas:  '140100'
              8.1  Registro Compras: '080100'
              5.1  Libro Diario:     '050100'
              6.1  Libro Mayor:      '060100'
- OPER       : 1 dígito. '1' = la operación tuvo movimientos; '0' = sin movimientos.
- INDOPS     : 1 dígito. '1' = información del periodo; '0' = sin información.
- MONEDA     : 1 dígito. '1' = moneda nacional (PEN); '2' = USD; '0' = ambas.
- MIX        : 1 dígito. '1' = info que NO afecta libros válidos. '0' opuesto.
              Para envío inicial normal usamos '1'.

Ejemplo:
    LE20131312955202604001401000111111.txt
    └─┬┘└────┬────┘└──┬───┘└──┬─┘│││││
      │     │       │      │   │││││
      LE    RUC     Período Libro │││││
            (11)    YYYYMM00 14.1 OPER│││
                              (6)   INDOPS
                                    │││
                                    MON
                                    │
                                    MIX

(Documentación SUNAT vigente: RS 286-2009 y modificatorias.)
"""

from __future__ import annotations

# Códigos SUNAT de libros (sub-libros) tal como aparecen en el nombre del archivo PLE.
LIBRO_VENTAS_14_1 = "140100"
LIBRO_COMPRAS_8_1 = "080100"
LIBRO_COMPRAS_8_2 = "080200"  # No domiciliados
LIBRO_DIARIO_5_1 = "050100"
LIBRO_DIARIO_SIMPL_5_3 = "050300"
LIBRO_MAYOR_6_1 = "060100"
LIBRO_INV_BAL_3_1 = "030100"
LIBRO_ACTIVOS_9_1 = "090100"
LIBRO_INV_FISICO_12_1 = "120100"
LIBRO_INV_VALORIZADO_13_1 = "130100"

# Periodicidad
PERIODICITY_MONTHLY = "monthly"  # YYYYMM00
PERIODICITY_ANNUAL = "annual"  # YYYY1200


def build_ple_filename(
    *,
    ruc: str,
    period_yyyymm: str,
    libro_code: str,
    has_movements: bool = True,
    has_info: bool = True,
    currency_indicator: str = "1",  # 1=PEN
    periodicity: str = PERIODICITY_MONTHLY,
) -> str:
    """Construye el nombre PLE SUNAT.

    Args:
        ruc:           RUC emisor (11 dígitos).
        period_yyyymm: '202604' (6 dígitos YYYYMM).
        libro_code:    código del libro (6 dígitos), e.g. LIBRO_VENTAS_14_1.
        has_movements: True → '1' (con movimientos). False → '0'.
        has_info:      True → '1' (con información). False → '0'.
        currency_indicator: '1' PEN, '2' USD, '0' ambas.
        periodicity:   'monthly' → DDsuffix '00' / 'annual' → DD '00' con mes 12.

    Returns:
        Nombre del archivo terminado en '.txt'.
    """
    if not ruc or len(ruc) != 11 or not ruc.isdigit():
        raise ValueError(f"ruc debe ser 11 dígitos, recibido: {ruc!r}")
    if not period_yyyymm or len(period_yyyymm) != 6 or not period_yyyymm.isdigit():
        raise ValueError(f"period_yyyymm debe ser YYYYMM (6 dígitos), recibido: {period_yyyymm!r}")
    if not libro_code or len(libro_code) != 6 or not libro_code.isdigit():
        raise ValueError(f"libro_code debe ser 6 dígitos, recibido: {libro_code!r}")
    if currency_indicator not in ("0", "1", "2"):
        raise ValueError(f"currency_indicator debe ser 0/1/2, recibido: {currency_indicator!r}")

    year = period_yyyymm[:4]
    month = period_yyyymm[4:]

    if periodicity == PERIODICITY_ANNUAL:
        period_full = f"{year}1200"
    else:
        period_full = f"{year}{month}00"

    oper = "1" if has_movements else "0"
    info = "1" if has_info else "0"
    mix = "1"  # envío normal

    return f"LE{ruc}{period_full}{libro_code}{oper}{info}{currency_indicator}{mix}.txt"
