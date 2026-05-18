# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - EDI núcleo (UBL 2.1 + firma XAdES-BES)",
    "summary": "Generación de UBL 2.1 SUNAT para Factura tipo 01, firma "
    "XAdES-BES con python-xmlsec, modelo l10n_pe_edi.document, "
    "campos de certificado en res.company. Transport-agnostic — "
    "la entrega a SUNAT vive en l10n_pe_edi_transport_sunat_soap.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_taxes_extras",
        "l10n_pe_detracciones",
    ],
    "external_dependencies": {
        "python": ["lxml", "xmlsec", "qrcode"],
    },
    "data": [
        "security/ir.model.access.csv",
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
