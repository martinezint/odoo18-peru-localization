# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


class L10nPeEdiDocument(models.Model):
    _inherit = "l10n.pe.edi.document"

    sunat_cdr = fields.Binary(
        string="CDR SUNAT (XML)",
        attachment=True,
        readonly=True,
        help="Constancia de Recepción devuelta por SUNAT tras sendBill.",
    )
    sunat_cdr_filename = fields.Char(
        string="Nombre CDR",
        readonly=True,
    )
    sunat_response_code = fields.Char(
        string="Código respuesta SUNAT",
        readonly=True,
        help="0 = aceptado, 100-1999 rechazado, 2000-3999 observado, 4000+ error.",
    )
    sunat_response_description = fields.Char(
        string="Descripción respuesta SUNAT",
        readonly=True,
    )
    sunat_sent_at = fields.Datetime(
        string="Enviado a SUNAT",
        readonly=True,
    )
