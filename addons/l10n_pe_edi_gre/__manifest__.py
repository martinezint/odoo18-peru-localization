# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - GRE 2.0: REST + UBL DespatchAdvice (Remitente)",
    "summary": "Cliente REST + OAuth2 SUNAT GRE 2.0 + UBL DespatchAdvice 2.1 "
    "para GRE Remitente desde stock.picking. Token cache con "
    "refresh. Métodos send_gre, get_status, download_file. "
    "v1: infra REST + builder GRE Remitente. GRE Transportista "
    "(31) usa la misma infra REST; UBL queda para v2.",
    "version": "18.0.0.2.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_edi",
        "stock",
    ],
    "external_dependencies": {
        "python": ["httpx", "lxml"],
    },
    "data": [
        "data/ir_cron_data.xml",
        "views/res_company_views.xml",
        "views/l10n_pe_edi_document_views.xml",
        "views/stock_picking_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
