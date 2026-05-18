# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - PCGE 2019 (completar core + posiciones fiscales por régimen)",
    "summary": "Posiciones fiscales por régimen tributario (General/MYPE/RER/NRUS), "
    "cuentas analíticas elemento 9 y de orden faltantes en core, "
    "auto-install del chart en empresas peruanas.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_base_extras",
        "l10n_pe",  # explícito: extendemos su chart template
        "account",
    ],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        "views/account_fiscal_position_views.xml",
    ],
    "demo": [],
    "post_init_hook": "_l10n_pe_coa_post_init",
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
