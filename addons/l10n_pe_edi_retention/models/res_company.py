# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_pe_retention_threshold = fields.Monetary(
        string="Umbral retención (S/)",
        default=700.0,
        currency_field="currency_id",
        help="SUNAT: la retención de IGV aplica solo cuando el monto facturado "
        "supera este umbral (vigente: S/700.00).",
    )
    l10n_pe_retention_rate = fields.Float(
        string="% Retención",
        default=3.0,
        digits=(5, 2),
        help="Porcentaje a retener sobre el subtotal sin IGV. Régimen general: 3%.",
    )
    l10n_pe_retention_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario de retenciones",
        help="Diario donde se contabilizan los comprobantes de retención emitidos.",
    )
    l10n_pe_retention_serie = fields.Char(
        string="Serie comprobante retención",
        default="R001",
        help="Serie SUNAT para los comprobantes de retención (4 caracteres).",
    )
