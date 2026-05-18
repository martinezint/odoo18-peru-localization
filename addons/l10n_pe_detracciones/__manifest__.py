# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Sistema de Detracciones (SPOT)",
    "summary": "Flujo completo de detracciones: cálculo por Anexo SUNAT, constancia, asiento al pago en Banco de la Nación",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": ['l10n_pe_taxes_extras', 'account'],
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
