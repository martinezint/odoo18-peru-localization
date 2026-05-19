# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Doble apunte PCGE Clase 6 ↔ Clase 9 (vía 79)",
    "summary": "Genera automáticamente el asiento contrapartida en cuentas "
    "de clase 9 (gastos por función / centros de costo) y cuenta "
    "79 (cargas imputables), tal como exige el PCGE 2019 y la "
    "normativa SUNAT para empresas obligadas a llevar contabilidad "
    "completa con PLE Diario.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/martinezint/odoo18-peru-localization",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_coa_pcge2019",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_company_views.xml",
        "views/account_move_views.xml",
        "wizards/double_entry_batch_wizard_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
