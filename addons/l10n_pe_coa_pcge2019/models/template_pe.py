# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Extensiones al chart template 'pe' de core l10n_pe.

Cuando dos módulos contribuyen al mismo template, Odoo 18 los mergea. Este
módulo añade cuentas faltantes (elemento 9 mayormente) y nuevas posiciones
fiscales por régimen tributario, sin tocar las 1229 cuentas existentes.
"""

from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("pe", "account.account")
    def _get_pe_account_account_pcge2019(self):
        return self._parse_csv(
            "pe",
            "account.account",
            module="l10n_pe_coa_pcge2019",
        )

    @template("pe", "account.fiscal.position")
    def _get_pe_fiscal_position_pcge2019(self):
        return self._parse_csv(
            "pe",
            "account.fiscal.position",
            module="l10n_pe_coa_pcge2019",
        )
