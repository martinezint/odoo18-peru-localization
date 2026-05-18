# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Sistema de Detracciones (SPOT) - tracking básico",
    "summary": "Catálogo SUNAT R.S. 183-2004 (Anexos 2/3), código de detracción "
               "en product.template, cálculo automático de monto detraído y "
               "constancia manual en account.move. (v1: tracking sin "
               "automatización de wizard de pago — eso vendrá en v2.)",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_taxes_extras",
        "account",
        "product",
    ],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_pe_detraccion_code_data.xml",
        "views/l10n_pe_detraccion_code_views.xml",
        "views/product_template_views.xml",
        "views/account_move_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
