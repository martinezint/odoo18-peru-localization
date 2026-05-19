# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Catálogo UBIGEO INEI: jerarquía Departamento → Provincia → Distrito.

UBIGEO = 6 dígitos:
  - Pos 1-2: código departamento (15 = Lima)
  - Pos 3-4: código provincia    (01 = Lima provincia)
  - Pos 5-6: código distrito     (01 = Lima distrito, Cercado)
  Ej: 150101 = Lima/Lima/Lima
      150122 = Lima/Lima/Pueblo Libre
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L10nPeUbigeo(models.Model):
    _name = "l10n.pe.ubigeo"
    _description = "UBIGEO INEI (Perú)"
    _order = "code"
    _rec_name = "display_name"

    code = fields.Char(
        string="Código UBIGEO",
        required=True,
        size=6,
        index=True,
        help="6 dígitos: 2 departamento + 2 provincia + 2 distrito.",
    )
    department = fields.Char(string="Departamento", required=True)
    province = fields.Char(string="Provincia", required=True)
    district = fields.Char(string="Distrito", required=True)
    active = fields.Boolean(default=True)

    display_name = fields.Char(compute="_compute_display_name", store=True, index=True)

    _sql_constraints = [
        ("code_unique", "UNIQUE(code)", "El código UBIGEO ya existe."),
    ]

    @api.depends("code", "department", "province", "district")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"[{rec.code}] {rec.district} / {rec.province} / {rec.department}"
                if rec.code
                else ""
            )

    @api.constrains("code")
    def _check_code_format(self):
        for rec in self:
            if not rec.code or len(rec.code) != 6 or not rec.code.isdigit():
                raise ValidationError(_("El UBIGEO debe ser 6 dígitos numéricos: %s") % rec.code)

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Búsqueda por código exacto, distrito, provincia o departamento."""
        args = list(args or [])
        if name:
            domain = [
                "|",
                "|",
                "|",
                ("code", "=", name),
                ("district", operator, name),
                ("province", operator, name),
                ("department", operator, name),
            ]
            recs = self.search(domain + args, limit=limit)
            return [(r.id, r.display_name) for r in recs]
        return super().name_search(name, args, operator, limit)
