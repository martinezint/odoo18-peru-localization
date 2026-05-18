# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - SIRE (RVIE + RCE) — infraestructura REST",
    "summary": "Cliente REST + OAuth2 a SUNAT SIRE (api-sire.sunat.gob.pe). "
    "Métodos para solicitar propuestas RCE (compras) y RVIE "
    "(ventas) y polling de tickets. Modelo l10n.pe.sire.period "
    "para tracking por período YYYYMM. v1: infraestructura + "
    "tickets. Conciliación con account.move y aceptación final "
    "vendrán en módulo siguiente.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_edi",
    ],
    "external_dependencies": {
        "python": ["httpx"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/res_company_views.xml",
        "views/l10n_pe_sire_period_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
