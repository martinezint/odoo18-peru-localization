# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


L10N_PE_TAX_KIND_SELECTION = [
    ("retencion_igv", "Retención IGV"),
    ("percepcion_igv", "Percepción IGV"),
    ("icbper", "ICBPER (Impuesto a las Bolsas Plásticas)"),
    ("ivap", "IVAP (Arroz Pilado)"),
    ("isc_al_valor", "ISC - Al Valor"),
    ("isc_especifico", "ISC - Específico"),
    ("isc_al_valor_cigarrillos", "ISC - Al Valor Cigarrillos"),
]


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_pe_tax_kind = fields.Selection(
        selection=L10N_PE_TAX_KIND_SELECTION,
        string="Tipo de impuesto PE",
        help="Clasificación interna del impuesto peruano para reportes, "
             "EDI y filtrado en vistas. Vacío = impuesto estándar IGV/ISC "
             "no clasificado (caso default).",
    )
