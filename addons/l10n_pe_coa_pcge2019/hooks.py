# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Post-install hook que aplica el chart 'pe' (con nuestros extras ya merged)
a cada empresa peruana que aún no tiene chart asignado."""

import logging

_logger = logging.getLogger(__name__)


def _l10n_pe_coa_post_init(env):
    """Aplica el chart template 'pe' a empresas PE sin chart.

    Idempotente: empresas con chart_template ya asignado se omiten.
    Cuando un usuario instala este módulo en una BD pre-existente con varias
    empresas, las peruanas reciben el chart automáticamente y aparecen las
    posiciones fiscales nuevas por régimen.
    """
    ChartTemplate = env["account.chart.template"]
    Company = env["res.company"]
    # res.company.country_id es computed (no stored) en Odoo 18, no se puede
    # filtrar por él directamente — vamos por partner_id.country_id que sí
    # está stored en res.partner.
    peru_companies = Company.search([("partner_id.country_id.code", "=", "PE")])
    if not peru_companies:
        _logger.info("l10n_pe_coa_pcge2019: no hay empresas peruanas, hook noop.")
        return

    for company in peru_companies:
        if company.chart_template:
            _logger.info(
                "l10n_pe_coa_pcge2019: empresa %s ya tiene chart %s, omitida.",
                company.name,
                company.chart_template,
            )
            continue
        _logger.info("l10n_pe_coa_pcge2019: aplicando chart 'pe' a empresa %s.", company.name)
        try:
            ChartTemplate.try_loading("pe", company=company, install_demo=False)
        except Exception:
            _logger.exception("Fallo aplicando chart 'pe' a empresa %s", company.name)
            # No re-raise: queremos que la instalación del módulo prosiga incluso
            # si una empresa falla. El usuario puede aplicar manualmente después.
