# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.ubl_parser import parse_ubl

_logger = logging.getLogger(__name__)


class L10nPeUploadSupplierXml(models.TransientModel):
    _name = "l10n.pe.upload.supplier.xml"
    _description = "Subir XML UBL de proveedor → crear borrador de factura"

    xml_file = fields.Binary(
        string="Archivo XML UBL 2.1",
        required=True,
        attachment=False,
    )
    xml_filename = fields.Char(string="Nombre del archivo")
    auto_create_partner = fields.Boolean(
        string="Crear partner si no existe",
        default=True,
        help="Si el RUC del proveedor no se encuentra, crea un partner nuevo "
             "como borrador (sin confirmar). Si se desactiva, falla con error.",
    )

    def action_parse_and_create(self):
        """Parsea el XML y crea (o intenta crear) un account.move borrador.

        Devuelve una acción que abre el move recién creado.
        """
        self.ensure_one()
        if not self.xml_file:
            raise UserError(_("Sube el archivo XML primero."))

        try:
            xml_bytes = base64.b64decode(self.xml_file)
        except Exception as exc:
            raise UserError(_("No pude decodificar el archivo: %s") % exc) from exc

        parsed = parse_ubl(xml_bytes)
        if not parsed.supplier_ruc:
            raise UserError(_(
                "El XML no contiene el RUC del proveedor "
                "(cac:AccountingSupplierParty)."
            ))
        if not parsed.document_number:
            raise UserError(_("El XML no contiene número de documento (cbc:ID)."))

        partner = self._find_or_create_partner(parsed)
        currency = self._resolve_currency(parsed.currency)
        move = self._create_draft_move(parsed, partner, currency)
        self._attach_xml(move, xml_bytes)

        # Notificación + abrir el move
        return {
            "type": "ir.actions.act_window",
            "name": _("Factura borrador creada"),
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "target": "current",
        }

    # ─── Resolución de partner ─────────────────────────────────────────

    def _find_or_create_partner(self, parsed):
        Partner = self.env["res.partner"]
        ruc = parsed.supplier_ruc.strip()
        existing = Partner.search([("vat", "=", ruc)], limit=1)
        if existing:
            return existing
        if not self.auto_create_partner:
            raise UserError(_(
                "El RUC %s no está registrado y la opción 'Crear partner' está desactivada."
            ) % ruc)

        # Crear partner borrador con datos mínimos del XML
        it_ruc = self.env.ref("l10n_pe.it_RUC", raise_if_not_found=False)
        peru = self.env.ref("base.pe", raise_if_not_found=False)
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

    # ─── Resolución de moneda ──────────────────────────────────────────

    def _resolve_currency(self, code: str):
        currency = self.env["res.currency"].search([("name", "=", code)], limit=1)
        if not currency:
            currency = self.env["res.currency"].with_context(
                active_test=False
            ).search([("name", "=", code)], limit=1)
            if currency and not currency.active:
                currency.active = True
        if not currency:
            raise UserError(_("Moneda '%s' no encontrada en Odoo.") % code)
        return currency

    # ─── Creación del move ─────────────────────────────────────────────

    def _create_draft_move(self, parsed, partner, currency):
        # Tipo de comprobante SUNAT → move_type Odoo
        # 01 Factura → in_invoice
        # 03 Boleta → in_invoice (raro recibirlas, pero válido)
        # 07 Nota Crédito → in_refund
        # 08 Nota Débito → in_invoice (o in_debit_note si Odoo lo soporta)
        type_code = parsed.document_type_code
        if type_code == "07":
            move_type = "in_refund"
        else:
            move_type = "in_invoice"

        Move = self.env["account.move"].with_company(self.env.company)
        line_vals = [self._build_line_vals(line) for line in parsed.lines]
        move = Move.create({
            "move_type": move_type,
            "partner_id": partner.id,
            "invoice_date": parsed.issue_date,
            "currency_id": currency.id,
            "ref": parsed.document_number,
            "invoice_line_ids": line_vals,
        })
        return move

    def _build_line_vals(self, line):
        return (0, 0, {
            "name": line.description or _("Sin descripción"),
            "quantity": float(line.quantity),
            "price_unit": float(line.price_unit),
            "tax_ids": [],  # taxes no se importan en v1 — el contador las añade
        })

    # ─── Adjuntar XML al move ──────────────────────────────────────────

    def _attach_xml(self, move, xml_bytes):
        self.env["ir.attachment"].create({
            "name": self.xml_filename or f"{move.ref or 'invoice'}.xml",
            "datas": base64.b64encode(xml_bytes),
            "res_model": "account.move",
            "res_id": move.id,
            "mimetype": "application/xml",
        })
