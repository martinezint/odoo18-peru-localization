# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_pe_regimen_tributario = fields.Selection(
        related="company_id.l10n_pe_regimen_tributario",
        readonly=False,
    )
    l10n_pe_apisnet_token = fields.Char(
        related="company_id.l10n_pe_apisnet_token",
        readonly=False,
    )
