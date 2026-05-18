# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Generador de QR para la representación impresa SUNAT.

RS 097-2012-SUNAT define el contenido del QR de un comprobante electrónico:
campos pipe-separados en una sola línea:

    RUC | TIPO_DOC | SERIE | NUMERO | IGV | TOTAL | FECHA_EMISION
        | TIPO_DOC_CLIENTE | NUMERO_DOC_CLIENTE | HASH

Donde:
- RUC: 11 dígitos del emisor.
- TIPO_DOC: catálogo 01 SUNAT (01 Factura, 03 Boleta, 07 NC, 08 ND).
- SERIE: serie del comprobante (4 chars típico, ej F001).
- NUMERO: número correlativo (sin ceros a la izquierda).
- IGV: importe total del IGV (2 decimales).
- TOTAL: importe total del comprobante (2 decimales).
- FECHA_EMISION: YYYY-MM-DD.
- TIPO_DOC_CLIENTE: catálogo 06 (1 DNI, 6 RUC, 4 CE, 0 si no hay).
- NUMERO_DOC_CLIENTE: número del documento del cliente.
- HASH: valor digest de la firma XAdES (truncado típicamente a la SignatureValue).

El QR se imprime en la representación impresa para que SUNAT/cliente puedan
verificar autenticidad escaneándolo.
"""
from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from typing import Optional

import qrcode


def build_qr_data(
    *,
    ruc: str,
    doc_type_code: str,
    serie: str,
    number: str,
    igv: Decimal,
    total: Decimal,
    issue_date: date,
    customer_doc_type_code: str,
    customer_doc_number: str,
    hash_value: str,
) -> str:
    """Construye el string canonical para el QR según RS 097-2012."""
    parts = [
        (ruc or "").strip(),
        doc_type_code or "",
        (serie or "").strip(),
        (number or "").strip().lstrip("0") or "0",
        _fmt(igv),
        _fmt(total),
        issue_date.isoformat() if issue_date else "",
        customer_doc_type_code or "0",
        (customer_doc_number or "").strip(),
        (hash_value or "").strip(),
    ]
    return "|".join(parts)


def build_qr_png_bytes(data: str, box_size: int = 5, border: int = 2) -> bytes:
    """Renderiza un QR como PNG bytes. data: el string a codificar."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fmt(value, decimals: int = 2) -> str:
    if value is None:
        return f"{Decimal('0'):.{decimals}f}"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.{decimals}f}"
