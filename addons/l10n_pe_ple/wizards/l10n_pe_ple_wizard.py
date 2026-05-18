# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import io

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.ple_5_1_diario import Ple5_1Generator
from ..services.ple_8_1_compras import Ple8_1Generator
from ..services.ple_14_1_ventas import Ple14_1Generator
from ..services.ple_filename import (
    LIBRO_COMPRAS_8_1,
    LIBRO_DIARIO_5_1,
    LIBRO_VENTAS_14_1,
    build_ple_filename,
)

LIBRO_SELECTION = [
    ("14_1", "14.1 — Registro de Ventas e Ingresos"),
    ("8_1", "8.1 — Registro de Compras"),
    ("5_1", "5.1 — Libro Diario"),
]


# Mapeo libro → (Generator class, código SUNAT)
_LIBRO_DISPATCH = {
    "14_1": (Ple14_1Generator, LIBRO_VENTAS_14_1),
    "8_1": (Ple8_1Generator, LIBRO_COMPRAS_8_1),
    "5_1": (Ple5_1Generator, LIBRO_DIARIO_5_1),
}


class L10nPePleWizard(models.TransientModel):
    _name = "l10n.pe.ple.wizard"
    _description = "Generador de PLE (SUNAT)"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    period_yyyymm = fields.Char(
        string="Período (YYYYMM)",
        required=True,
        default=lambda self: fields.Date.today().strftime("%Y%m"),
        size=6,
    )
    libro = fields.Selection(
        selection=LIBRO_SELECTION,
        required=True,
        default="14_1",
    )

    file_data = fields.Binary(readonly=True, attachment=False)
    file_name = fields.Char(readonly=True)
    line_count = fields.Integer(readonly=True)

    def action_generate(self):
        """Genera el TXT en memoria y muestra el wizard con link de descarga."""
        self.ensure_one()
        if (
            not self.period_yyyymm
            or len(self.period_yyyymm) != 6
            or not self.period_yyyymm.isdigit()
        ):
            raise UserError(_("Período debe ser YYYYMM (6 dígitos)."))
        if not self.company_id.vat:
            raise UserError(_("La empresa %s no tiene RUC configurado.") % self.company_id.name)
        if self.libro not in _LIBRO_DISPATCH:
            raise UserError(_("Libro %s no soportado.") % self.libro)

        GeneratorCls, libro_code = _LIBRO_DISPATCH[self.libro]
        gen = GeneratorCls(self.env, self.company_id, self.period_yyyymm)

        buf = io.BytesIO()
        count = gen.generate_to_file(buf)

        filename = build_ple_filename(
            ruc=self.company_id.vat.strip(),
            period_yyyymm=self.period_yyyymm,
            libro_code=libro_code,
            has_movements=count > 0,
            has_info=count > 0,
        )
        self.write(
            {
                "file_data": base64.b64encode(buf.getvalue()),
                "file_name": filename,
                "line_count": count,
            }
        )

        # Re-abre el wizard con el archivo listo para descargar
        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n.pe.ple.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
