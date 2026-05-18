# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Representación impresa con QR (RS 097-2012)",
    "summary": "QR code generator según RS 097-2012 (RUC|TipoDoc|Serie|Numero|"
    "IGV|Total|FechaEmision|TipoDocCli|NumeroCli|Hash). Extensión "
    "del reporte de factura QWeb para añadir QR + hash + leyenda "
    "'Representación impresa de la <TipoDoc> Electrónica'. "
    "Aplica a Factura, Boleta, NC, ND.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_edi",
        "web",
    ],
    "external_dependencies": {
        "python": ["qrcode"],
    },
    "data": [
        "reports/report_invoice_l10n_pe.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
