# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Impuestos adicionales (retenciones, percepciones, ICBPER, IVAP, ISC)",
    "summary": "Tax groups y account.tax para retenciones (1.5/3/6%), "
    "percepciones (2%), ICBPER (S/0.50 fijo), IVAP (4%) e ISC "
    "(3 sistemas SUNAT catálogo 08). Campo l10n_pe_tax_kind para "
    "clasificación. Post-init re-aplica chart a empresas PE.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_coa_pcge2019",
    ],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        "views/account_tax_views.xml",
    ],
    "demo": [],
    "post_init_hook": "_l10n_pe_taxes_post_init",
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
