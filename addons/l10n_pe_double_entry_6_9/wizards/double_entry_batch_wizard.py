# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Wizard masivo para regularizar dobles apuntes pendientes.

Útil cuando:
  - Se instala el módulo en una BD con histórico de facturas pre-existente
  - Se desactiva el flag auto y se quiere correr el batch a fin de mes
  - Algunos moves quedaron sin contrapartida por configuración faltante
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nPeDoubleEntryBatchWizard(models.TransientModel):
    _name = "l10n.pe.double.entry.batch.wizard"
    _description = "Generar dobles apuntes 6↔9 pendientes (batch)"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string="Desde",
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
    )
    date_to = fields.Date(
        string="Hasta",
        required=True,
        default=fields.Date.context_today,
    )

    # ─── Resultados ───────────────────────────────────────────────────
    processed_count = fields.Integer(readonly=True)
    generated_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    error_log = fields.Text(readonly=True)

    def action_run(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("La fecha 'Desde' debe ser anterior a 'Hasta'."))
        Move = self.env["account.move"]
        candidates = Move.search(
            [
                ("company_id", "=", self.company_id.id),
                ("state", "=", "posted"),
                ("date", ">=", self.date_from),
                ("date", "<=", self.date_to),
                ("l10n_pe_double_entry_move_id", "=", False),
                ("l10n_pe_double_entry_origin_id", "=", False),
            ]
        )
        processed = 0
        generated = 0
        errors = []
        for move in candidates:
            processed += 1
            if move._l10n_pe_get_class_6_total() <= 0:
                continue
            try:
                result = move._l10n_pe_generate_double_entry(raise_on_missing=True)
            except Exception as exc:
                errors.append(f"{move.display_name}: {exc}")
                continue
            if result:
                generated += 1

        self.write(
            {
                "processed_count": processed,
                "generated_count": generated,
                "skipped_count": processed - generated - len(errors),
                "error_log": "\n".join(errors) if errors else False,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n.pe.double.entry.batch.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
