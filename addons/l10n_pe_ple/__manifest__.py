# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - PLE 5.x: Registro de Ventas (14.1) y Compras (8.1)",
    "summary": "Generación de TXT PLE 5.x con naming SUNAT estricto. v1: "
    "Registro de Ventas 14.1 y Registro de Compras 8.1 desde "
    "account.move. Wizard con descarga directa. Streaming para "
    "BDs grandes. Libros Diario (5.x), Mayor (6.1) e Inventarios "
    "(3.x) quedan para v2.",
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
        "security/ir.model.access.csv",
        "wizards/l10n_pe_ple_wizard_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
