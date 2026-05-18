# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Representación impresa (PDF)",
    "summary": "Representación impresa de factura, boleta, NC, ND, guía y comprobantes con QR según RS 097-2012 y hash en pie",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": ['l10n_pe_edi', 'web'],
    "external_dependencies": {
        "python": ['qrcode'],
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
