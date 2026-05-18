# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - POS con facturación electrónica",
    "summary": "Extensión del l10n_pe_pos core con emisión EDI de boletas y RC al cierre de caja. Numeración offline-safe.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": ['l10n_pe_edi_transport_sunat_soap', 'l10n_pe_pos', 'point_of_sale'],
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
