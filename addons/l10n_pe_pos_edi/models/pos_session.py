# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, models


class PosSession(models.Model):
    _inherit = "pos.session"

    def action_l10n_pe_open_rc_wizard(self):
        """Abre el wizard de RC pre-cargado con la fecha del cierre de sesión."""
        self.ensure_one()
        reference_date = (self.stop_at or self.start_at).date() if (self.stop_at or self.start_at) else None
        ctx = {
            "default_company_id": self.company_id.id,
            "default_reference_date": reference_date,
        }
        return {
            "type": "ir.actions.act_window",
            "name": _("Generar RC del cierre"),
            "res_model": "l10n.pe.rc.wizard",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }
