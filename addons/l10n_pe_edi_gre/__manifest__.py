# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - GRE 2.0: infraestructura REST + OAuth2",
    "summary": "Cliente REST + OAuth2 client_credentials a SUNAT GRE 2.0 "
               "(api-cpe.sunat.gob.pe). Token cache con refresh automático. "
               "Métodos POST /comprobantes/<numDoc> y GET /envios/<ticket>. "
               "Soporta Remitente (09) y Transportista (31). "
               "v1: sólo transport. UBL builder de DespatchAdvice + integración "
               "stock.picking vendrán en módulo siguiente.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_edi",  # reusa l10n.pe.edi.document como base
    ],
    "external_dependencies": {
        "python": ["httpx"],
    },
    "data": [
        "views/res_company_views.xml",
        "views/l10n_pe_edi_document_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
