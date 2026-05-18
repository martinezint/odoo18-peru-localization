# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Bandeja de comprobantes electrónicos recibidos",
    "summary": "Sube el XML UBL 2.1 del proveedor y crea un borrador de "
    "factura de compra. Auto-matches el partner por RUC y adjunta "
    "el XML al move para trazabilidad. (v1: solo upload manual; "
    "mail alias y validación de firma vendrán después con l10n_pe_edi.)",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_base_extras",
        "account",
    ],
    "external_dependencies": {
        "python": ["lxml"],
    },
    "data": [
        "security/ir.model.access.csv",
        "wizards/upload_supplier_xml_views.xml",
        "views/account_move_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
