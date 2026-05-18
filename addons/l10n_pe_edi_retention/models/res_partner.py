# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_pe_retention_applies = fields.Boolean(
        string="Sujeto a Retención IGV",
        help="Marcar para proveedores del Régimen General sujetos a retención IGV. "
        "Al pagar sus facturas, el wizard sugerirá calcular y generar el "
        "comprobante de retención automáticamente.",
    )
