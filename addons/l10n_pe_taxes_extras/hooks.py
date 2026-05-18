# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Re-aplica chart 'pe' a empresas peruanas que ya lo tenían instalado, para
que reciban los nuevos tax groups e impuestos que este módulo contribuye."""

import logging

_logger = logging.getLogger(__name__)


def _l10n_pe_taxes_post_init(env):
    """Idempotente: try_loading detecta lo que falta y lo añade."""
    ChartTemplate = env["account.chart.template"]
    Company = env["res.company"]
    # Solo empresas PE con chart 'pe' ya aplicado (las que no lo tienen serán
    # cubiertas por el hook de l10n_pe_coa_pcge2019).
    pe_companies = Company.search(
        [
            ("partner_id.country_id.code", "=", "PE"),
            ("chart_template", "=", "pe"),
        ]
    )
    for company in pe_companies:
        _logger.info(
            "l10n_pe_taxes_extras: re-aplicando chart 'pe' a %s para cargar nuevos taxes.",
            company.name,
        )
        try:
            ChartTemplate.try_loading("pe", company=company, install_demo=False)
        except Exception:
            _logger.exception("Fallo re-aplicando chart 'pe' a empresa %s", company.name)
