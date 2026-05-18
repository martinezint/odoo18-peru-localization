# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - PLE 5.x (Programa de Libros Electrónicos)",
    "summary": "Generación TXT PLE 5.x: 14.1 (Ventas), 8.1/8.2/8.3 (Compras), 5.1/5.3 (Diario), 6.1 (Mayor), 3.x (Inventarios y Balances). Streaming para BD grandes.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": ['l10n_pe_coa_pcge2019', 'date_range'],
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
