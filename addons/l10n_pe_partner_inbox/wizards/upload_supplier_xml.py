# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.inbox_processor import process_xml_bytes


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
        """Parsea el XML y crea (o intenta crear) un account.move borrador."""
        self.ensure_one()
        if not self.xml_file:
            raise UserError(_("Sube el archivo XML primero."))
        try:
            xml_bytes = base64.b64decode(self.xml_file)
        except Exception as exc:
            raise UserError(_("No pude decodificar el archivo: %s") % exc) from exc

        move = process_xml_bytes(
            self.env,
            xml_bytes,
            xml_filename=self.xml_filename or "",
            auto_create_partner=self.auto_create_partner,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Factura borrador creada"),
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "target": "current",
        }
