# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - EDI núcleo (UBL 2.1 + firma XAdES-BES)",
    "summary": "Núcleo de facturación electrónica: generación UBL 2.1, firma XAdES-BES con python-xmlsec, modelo l10n_pe_edi.document, wizard de envío. Transport-agnostic.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": ['l10n_pe_taxes_extras', 'l10n_pe_detracciones'],
    "external_dependencies": {
        "python": ['lxml', 'xmlsec', 'qrcode'],
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
