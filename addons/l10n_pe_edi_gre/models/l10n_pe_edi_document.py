# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class L10nPeEdiDocument(models.Model):
    _inherit = "l10n.pe.edi.document"

    gre_ticket = fields.Char(
        string="GRE numTicket",
        readonly=True,
        copy=False,
        help="Ticket asíncrono devuelto por SUNAT al enviar la GRE. "
             "Se usa para consultar el estado vía GET /envios/<ticket>.",
    )
    gre_ind_estado = fields.Selection(
        selection=[
            ("01", "En proceso"),
            ("03", "Rechazado"),
            ("05", "Aceptado"),
            ("11", "Anulado"),
        ],
        string="GRE indEstado",
        readonly=True,
        copy=False,
    )
    gre_cdr = fields.Binary(
        string="GRE CDR (ZIP)",
        attachment=True,
        readonly=True,
        help="CDR (Constancia de Recepción) GRE devuelto por SUNAT cuando el "
             "documento es aceptado o rechazado.",
    )
    gre_cdr_filename = fields.Char(
        string="GRE CDR filename",
        readonly=True,
    )
    gre_sent_at = fields.Datetime(
        string="GRE enviado en",
        readonly=True,
        copy=False,
    )
    gre_last_status_check_at = fields.Datetime(
        string="GRE último status",
        readonly=True,
        copy=False,
    )

    # ─── Acciones GRE ──────────────────────────────────────────────

    def action_l10n_pe_gre_check_status(self):
        """Consulta el estado del ticket GRE en SUNAT y actualiza el doc."""
        for doc in self:
            doc._gre_check_status_one()
        return True

    def _gre_check_status_one(self):
        self.ensure_one()
        if not self.gre_ticket:
            raise UserError(_("Este documento no tiene ticket GRE."))

        client = self.company_id._get_l10n_pe_gre_rest_client()
        status = client.get_status(self.gre_ticket)
        vals = {
            "gre_ind_estado": status.ind_estado or False,
            "gre_last_status_check_at": fields.Datetime.now(),
        }
        # CDR llega en status.cdr_base64 cuando aceptado
        if status.is_accepted and status.cdr_base64:
            try:
                # cdr_base64 ya es base64; lo guardamos así directamente
                vals["gre_cdr"] = status.cdr_base64.encode("ascii")
                vals["gre_cdr_filename"] = f"R-{self.name}.zip" if self.name else "R-gre.zip"
                vals["state"] = "accepted"
            except Exception:
                _logger.exception("Fallo guardando CDR GRE para %s", self.name)
        elif status.is_rejected:
            vals["state"] = "rejected"
            err = status.error or {}
            vals["error_message"] = err.get("desError") or err.get("numError") or "Rechazado por SUNAT"
        elif status.is_cancelled:
            vals["state"] = "error"
            vals["error_message"] = _("GRE anulada en SUNAT")
        # is_in_process → state queda sin cambios
        self.write(vals)

    @api.model
    def _cron_poll_gre_tickets(self):
        """Cron: polling de GRE tickets en estado '01' (en proceso).

        Errores por doc se loggean; el cron no se detiene.
        Llamado por ir.cron 'Peru SUNAT: poll tickets GRE'.
        """
        pending = self.search([
            ("gre_ticket", "!=", False),
            ("gre_ind_estado", "=", "01"),
        ])
        if not pending:
            _logger.debug("cron_poll_gre_tickets: nada pendiente.")
            return
        _logger.info("cron_poll_gre_tickets: %d tickets GRE para polling.", len(pending))
        for doc in pending:
            try:
                doc._gre_check_status_one()
            except Exception:
                _logger.exception(
                    "Fallo polling GRE ticket %s (doc %s)",
                    doc.gre_ticket, doc.name,
                )
