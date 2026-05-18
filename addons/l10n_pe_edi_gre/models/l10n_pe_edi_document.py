# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


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
