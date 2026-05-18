# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


ANEXO_SELECTION = [
    ("2", "Anexo 2 - Bienes sujetos al SPOT"),
    ("3", "Anexo 3 - Servicios sujetos al SPOT"),
]


class L10nPeDetraccionCode(models.Model):
    """Catálogo SUNAT R.S. 183-2004 (y modificatorias) de bienes y servicios
    sujetos al Sistema de Pago de Obligaciones Tributarias (SPOT, detracciones).

    Cada código identifica un bien o servicio gravado y su porcentaje de
    detracción aplicable. Se asigna a `product.template` para que el cálculo
    de la detracción en `account.move` sea automático.
    """
    _name = "l10n.pe.detraccion.code"
    _description = "Código SUNAT de Detracción (SPOT)"
    _order = "anexo, code"
    _rec_name = "display_name"

    code = fields.Char(
        string="Código",
        required=True,
        size=3,
        help="Código SUNAT del bien/servicio (ej. '001', '012').",
    )
    name = fields.Char(
        string="Descripción",
        required=True,
        translate=True,
    )
    anexo = fields.Selection(
        selection=ANEXO_SELECTION,
        string="Anexo SUNAT",
        required=True,
    )
    percentage = fields.Float(
        string="% Detracción",
        required=True,
        digits=(5, 2),
        help="Porcentaje a aplicar sobre el TOTAL del comprobante "
             "(importe + IGV). Ej: 10.0 para 10%, 1.5 para 1.5%.",
    )
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("code", "name", "percentage")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name} ({rec.percentage}%)"

    _sql_constraints = [
        ("code_unique", "UNIQUE(code)",
         "El código de detracción debe ser único."),
    ]

    @api.constrains("percentage")
    def _check_percentage(self):
        for rec in self:
            if rec.percentage <= 0 or rec.percentage > 100:
                raise ValidationError(_(
                    "El porcentaje de detracción debe estar entre 0 y 100 (exclusive)."
                ))
