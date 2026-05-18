# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models

# Reutiliza la lista del módulo base_extras para mantener un solo punto
# de verdad sobre los regímenes válidos.
from odoo.addons.l10n_pe_base_extras.models.res_company import (
    REGIMEN_TRIBUTARIO_SELECTION,
)


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    l10n_pe_regimen_tributario = fields.Selection(
        selection=REGIMEN_TRIBUTARIO_SELECTION,
        string="Régimen Tributario",
        help="Régimen tributario SUNAT al que aplica esta posición fiscal. "
             "Vacío = aplica a cualquier régimen (comportamiento por defecto).",
    )
