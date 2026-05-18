# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Base extras (RUC, catálogos SUNAT, régimen tributario)",
    "summary": "Validación RUC/DNI/CE, régimen tributario en res.company, "
    "consulta RUC/DNI online vía apis.net.pe",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe",
        "l10n_latam_base",
        "l10n_latam_invoice_document",
        "base_vat",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "views/res_partner_views.xml",
        "views/res_company_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
