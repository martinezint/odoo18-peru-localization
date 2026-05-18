# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Tipo de cambio SBS",
    "summary": "Cron diario de tipo de cambio (USD/EUR/...) desde la "
               "Superintendencia de Banca, Seguros y AFP (SBS). "
               "Configurable por empresa: monedas, compra/venta, on/off.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_base_extras",
    ],
    "external_dependencies": {
        "python": ["requests", "lxml"],
    },
    "data": [
        "data/ir_cron_data.xml",
        "views/res_company_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
