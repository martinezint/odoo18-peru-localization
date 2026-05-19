# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
{
    "name": "Peru - Catálogo UBIGEO (INEI)",
    "summary": "Catálogo oficial de UBIGEOs peruanos (6 dígitos: "
    "DD departamento + PP provincia + CC distrito) para validación "
    "y autocompletado en partner y guías GRE. Incluye dataset semilla "
    "con Lima Metropolitana completa + capitales departamentales. "
    "El dataset completo (1,874 distritos) se importa via CSV "
    "extendiendo data/ con el archivo INEI oficial.",
    "version": "18.0.0.1.0",
    "category": "Accounting/Localizations/Peru",
    "author": "Marc Martínez & contributors",
    "website": "https://github.com/martinezint/odoo18-peru-localization",
    "license": "AGPL-3",
    "depends": [
        "base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_pe_ubigeo_views.xml",
        "data/l10n_pe_ubigeo_data.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "countries": ["pe"],
}
