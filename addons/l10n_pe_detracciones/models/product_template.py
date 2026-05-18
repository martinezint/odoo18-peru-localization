# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_pe_detraccion_code_id = fields.Many2one(
        comodel_name="l10n.pe.detraccion.code",
        string="Código de Detracción",
        help="Código SUNAT R.S. 183-2004 si el producto/servicio está sujeto a "
             "detracción. Vacío = no aplica.",
    )
