# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Base extras (RUC, catálogos SUNAT, régimen tributario)",
    "summary": "Validación RUC mod 11, catálogos SUNAT 02/07/08/09/12/17/51/52/53, régimen tributario en res.company, consulta RUC online",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": ['l10n_pe', 'l10n_latam_base', 'l10n_latam_invoice_document'],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        # "security/ir.model.access.csv",
        # "views/...",
    ],
    "demo": [
        # "demo/demo.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
