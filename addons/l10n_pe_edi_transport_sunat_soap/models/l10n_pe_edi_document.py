# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

    # ─── Async (sendSummary): RC y RA ─────────────────────────────────
    # Para documentos sync (Factura/Boleta/NC/ND) los fields de arriba
    # se llenan tras sendBill. Para documentos async (RC, RA), el flujo es:
    # 1. sendSummary → numTicket (se guarda en sunat_summary_ticket)
    # 2. polling getStatus(ticket) → CDR final cuando statusCode='0'

    sunat_summary_ticket = fields.Char(
        string="Ticket SUNAT (async)",
        readonly=True,
        copy=False,
        help="numTicket devuelto por sendSummary. Se consulta vía getStatus.",
    )
    sunat_summary_status_code = fields.Selection(
        selection=[
            ("0", "Procesado correctamente"),
            ("98", "En proceso"),
            ("99", "Proceso con errores"),
            ("90", "Error desconocido"),
        ],
        string="Estado async SUNAT",
        readonly=True,
        copy=False,
    )
    sunat_summary_last_check_at = fields.Datetime(
        string="Último polling",
        readonly=True,
        copy=False,
    )

    # ─── Acciones async (RC/RA) ─────────────────────────────────────

    def action_l10n_pe_send_summary(self):
        """Envía el XML firmado vía sendSummary (async, devuelve ticket)."""
        for doc in self:
            doc._send_summary_one()
        return True

    def _send_summary_one(self):
        self.ensure_one()
        if not self.xml_signed:
            raise UserError(_("No hay XML firmado en %s") % self.name)
        if self.sunat_summary_ticket:
            raise UserError(
                _(
                    "Este documento ya tiene un ticket (%s). Usa 'Consultar estado' "
                    "para chequear el resultado."
                )
                % self.sunat_summary_ticket
            )

        client = self.company_id._get_l10n_pe_sunat_soap_client()
        xml_filename = self.name
        zip_filename = xml_filename.replace(".xml", ".zip")
        xml_bytes = base64.b64decode(self.xml_signed)
        zip_bytes = client.zip_xml(xml_filename, xml_bytes)

        from ..services.sunat_soap import SunatSoapError

        try:
            ticket = client.send_summary(zip_filename, zip_bytes)
        except SunatSoapError as exc:
            self.write(
                {
                    "state": "error",
                    "error_message": str(exc),
                    "sunat_sent_at": fields.Datetime.now(),
                }
            )
            raise UserError(_("SUNAT rechazó el envío: %s") % exc) from exc

        self.write(
            {
                "sunat_summary_ticket": ticket,
                "sunat_summary_status_code": "98",  # en proceso
                "sunat_sent_at": fields.Datetime.now(),
                "state": "sent",
                "error_message": False,
            }
        )
        _logger.info("sendSummary OK para %s → ticket %s", self.name, ticket)

    def action_l10n_pe_check_summary_status(self):
        """Polling: consulta el estado del ticket y actualiza."""
        for doc in self:
            doc._check_summary_status_one()
        return True

    @api.model
    def _cron_poll_summary_tickets(self):
        """Cron: consulta el estado de todos los docs con ticket en '98'
        (en proceso). Errores por doc se loggean pero no detienen el cron.

        Llamado por ir.cron 'Peru SUNAT: poll tickets RC async' (data file).
        """
        pending = self.search(
            [
                ("sunat_summary_ticket", "!=", False),
                ("sunat_summary_status_code", "=", "98"),
            ]
        )
        if not pending:
            _logger.debug("cron_poll_summary_tickets: nada pendiente.")
            return
        _logger.info(
            "cron_poll_summary_tickets: %d tickets RC para polling.",
            len(pending),
        )
        for doc in pending:
            try:
                doc._check_summary_status_one()
            except Exception:
                _logger.exception(
                    "Fallo polling ticket %s (doc %s)",
                    doc.sunat_summary_ticket,
                    doc.name,
                )

    def _check_summary_status_one(self):
        self.ensure_one()
        if not self.sunat_summary_ticket:
            raise UserError(_("Este documento no tiene ticket async."))

        client = self.company_id._get_l10n_pe_sunat_soap_client()
        from ..services.cdr_parser import parse_cdr

        result = client.get_status_async(self.sunat_summary_ticket)
        status_code = result["status_code"]
        cdr_bytes = result["cdr_bytes"]

        vals = {
            "sunat_summary_status_code": status_code,
            "sunat_summary_last_check_at": fields.Datetime.now(),
        }
        if status_code == "0" and cdr_bytes:
            cdr = parse_cdr(cdr_bytes)
            vals.update(
                {
                    "sunat_cdr": base64.b64encode(cdr_bytes),
                    "sunat_cdr_filename": f"R-{self.name}",
                    "sunat_response_code": cdr.response_code,
                    "sunat_response_description": cdr.description,
                    "state": "accepted" if cdr.is_accepted or cdr.is_observed else "rejected",
                }
            )
        elif status_code in ("99", "90"):
            vals.update(
                {
                    "state": "error",
                    "error_message": _("Error async SUNAT código %s") % status_code,
                }
            )
        # status_code='98' → seguimos esperando, no cambia state
        self.write(vals)
