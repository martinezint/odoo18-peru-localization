# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - POS: Resumen Diario de Boletas (RC)",
    "summary": "Generador de Resumen Diario de Boletas (SUNAT SummaryDocuments) "
    "desde boletas posteadas en account.move. Wizard de generación "
    "+ extensión pos.session con botón 'Generar RC del cierre'. "
    "Reusa firma XAdES de l10n_pe_edi. v1: builder + wizard. "
    "Envío async vía sendSummary SOAP queda para v2.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_edi",
        "point_of_sale",
    ],
    "external_dependencies": {
        "python": ["lxml"],
    },
    "data": [
        "security/ir.model.access.csv",
        "wizards/l10n_pe_rc_wizard_views.xml",
        "views/pos_session_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
