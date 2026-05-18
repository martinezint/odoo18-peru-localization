# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Servicio compartido: dado un XML UBL → crea borrador account.move.

Extraído del wizard `l10n.pe.upload.supplier.xml` para reuso desde el
mail alias (`l10n.pe.partner.inbox.message`).
"""

from __future__ import annotations

import base64
import io
import logging
import zipfile

from odoo import _
from odoo.exceptions import UserError

from .ubl_parser import parse_ubl

_logger = logging.getLogger(__name__)


def process_xml_bytes(
    env, xml_bytes: bytes, *, xml_filename: str = "", auto_create_partner: bool = True
):
    """Procesa un XML UBL → crea (o intenta crear) un account.move borrador.

    Devuelve el `account.move` creado. Lanza `UserError` con mensaje legible
    si el XML es inválido o falta info crítica.
    """
    parsed = parse_ubl(xml_bytes)
    if not parsed.supplier_ruc:
        raise UserError(_("El XML no contiene el RUC del proveedor."))
    if not parsed.document_number:
        raise UserError(_("El XML no contiene número de documento."))

    partner = _find_or_create_partner(env, parsed, auto_create_partner)
    currency = _resolve_currency(env, parsed.currency)
    move = _create_draft_move(env, parsed, partner, currency)
    _attach_xml(env, move, xml_bytes, xml_filename or f"{parsed.document_number}.xml")
    return move


def extract_xml_payloads(attachments) -> list[tuple[str, bytes]]:
    """Itera attachments (lista de `ir.attachment`) y devuelve [(filename, bytes)].

    - Acepta `.xml` directos.
    - Si es `.zip`, lo abre y extrae los `.xml` internos.
    - Otros tipos se ignoran silenciosamente.
    """
    out = []
    for att in attachments:
        try:
            raw = base64.b64decode(att.datas) if isinstance(att.datas, (bytes, str)) else b""
        except Exception:
            _logger.exception("No pude decodificar attachment %s", att.name)
            continue
        name = (att.name or "").lower()
        if name.endswith(".xml"):
            out.append((att.name, raw))
            continue
        if name.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for member in zf.namelist():
                        if member.lower().endswith(".xml"):
                            out.append((member, zf.read(member)))
            except zipfile.BadZipFile:
                _logger.warning("Attachment %s no es un ZIP válido", att.name)
    return out


# ─── helpers (copiados del wizard para no acoplar) ────────────────────


def _find_or_create_partner(env, parsed, auto_create: bool):
    Partner = env["res.partner"]
    ruc = parsed.supplier_ruc.strip()
    existing = Partner.search([("vat", "=", ruc)], limit=1)
    if existing:
        return existing
    if not auto_create:
        raise UserError(_("El RUC %s no está registrado.") % ruc)
    it_ruc = env.ref("l10n_pe.it_RUC", raise_if_not_found=False)
    peru = env.ref("base.pe", raise_if_not_found=False)
    vals = {
        "name": parsed.supplier_name or _("Proveedor RUC %s") % ruc,
        "vat": ruc,
        "is_company": True,
        "supplier_rank": 1,
    }
    if it_ruc:
        vals["l10n_latam_identification_type_id"] = it_ruc.id
    if peru:
        vals["country_id"] = peru.id
    return Partner.create(vals)


def _resolve_currency(env, code: str):
    currency = (
        env["res.currency"].with_context(active_test=False).search([("name", "=", code)], limit=1)
    )
    if not currency:
        raise UserError(_("Moneda '%s' no encontrada en Odoo.") % code)
    if not currency.active:
        currency.active = True
    return currency


def _create_draft_move(env, parsed, partner, currency):
    move_type = "in_refund" if parsed.document_type_code == "07" else "in_invoice"
    Move = env["account.move"].with_company(env.company)
    line_vals = [
        (
            0,
            0,
            {
                "name": ln.description or _("Sin descripción"),
                "quantity": float(ln.quantity),
                "price_unit": float(ln.price_unit),
                "tax_ids": [],
            },
        )
        for ln in parsed.lines
    ]
    return Move.create(
        {
            "move_type": move_type,
            "partner_id": partner.id,
            "invoice_date": parsed.issue_date,
            "currency_id": currency.id,
            "ref": parsed.document_number,
            "invoice_line_ids": line_vals,
        }
    )


def _attach_xml(env, move, xml_bytes: bytes, filename: str):
    env["ir.attachment"].create(
        {
            "name": filename,
            "datas": base64.b64encode(xml_bytes),
            "res_model": "account.move",
            "res_id": move.id,
            "mimetype": "application/xml",
        }
    )
