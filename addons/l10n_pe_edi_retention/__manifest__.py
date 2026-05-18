# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Comprobantes de Retención (20) y Percepción (40)",
    "summary": "Modelos l10n.pe.retention y l10n.pe.perception con sus líneas "
    "(documentos de origen). UBL builders SUNAT específicos "
    "(namespace sac, esquemas Retention-1 y Perception-1). "
    "Reusa firma XAdES de l10n_pe_edi y transport SOAP de "
    "l10n_pe_edi_transport_sunat_soap.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/your-org/odoo-l10n-peru-ce",
    "license": "AGPL-3",
    "depends": [
        "l10n_pe_edi",
        "l10n_pe_edi_transport_sunat_soap",
        "l10n_pe_taxes_extras",
    ],
    "external_dependencies": {
        "python": ["lxml"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_pe_retention_views.xml",
        "views/l10n_pe_perception_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
