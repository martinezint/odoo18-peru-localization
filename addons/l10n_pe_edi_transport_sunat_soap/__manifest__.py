# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - EDI Transport: SUNAT directo SOAP",
    "summary": "Envío sincrónico a SUNAT vía SOAP (sendBill) para Factura/NC/ND. "
    "Empaqueta XML firmado en ZIP, autentica con usuario SOL "
    "(RUC+USER, password), parsea CDR de respuesta. BETA y producción.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_edi",
    ],
    "external_dependencies": {
        "python": ["zeep"],
    },
    "data": [
        "views/res_company_views.xml",
        "views/l10n_pe_edi_document_views.xml",
        "views/account_move_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
