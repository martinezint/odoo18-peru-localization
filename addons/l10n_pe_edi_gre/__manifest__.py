# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Guía de Remisión Electrónica GRE 2.0",
    "summary": "GRE 2.0 vía REST API + JWT Bearer, remitente y transportista, integración con stock.picking",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": ['l10n_pe_edi', 'stock'],
    "external_dependencies": {
        "python": ['httpx'],
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
