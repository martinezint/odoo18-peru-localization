# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Mail alias receivable para recibir XMLs de proveedores por email.

Flujo:
1. Configurar mail.alias apuntando a `l10n.pe.partner.inbox.message`
   (típicamente `factura.proveedor@dominio.com`).
2. Proveedor envía email con XML (o ZIP con XML) adjunto.
3. Cada email crea una `l10n.pe.partner.inbox.message` que:
   - Itera attachments, extrae XML válidos (.xml o .xml dentro de .zip)
   - Por cada XML, llama a `process_xml_bytes` (mismo flujo que el wizard)
   - Crea account.move borradores y los enlaza en `created_move_ids`
   - Si algún XML falla, registra el error en `processing_log` (NO re-raise)
4. El contador revisa los borradores creados y valida/postea.
"""

import logging

from odoo import _, api, fields, models

from ..services.inbox_processor import extract_xml_payloads, process_xml_bytes

_logger = logging.getLogger(__name__)


class L10nPePartnerInboxMessage(models.Model):
    _name = "l10n.pe.partner.inbox.message"
    _description = "Bandeja de XMLs recibidos por email (proveedores)"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"

    name = fields.Char(default=lambda self: _("Email recibido"), required=True)
    email_from = fields.Char()
    subject = fields.Char()
    state = fields.Selection(
        [
            ("draft", "Pendiente"),
            ("processed", "Procesado"),
            ("error", "Con errores"),
        ],
        default="draft",
        tracking=True,
    )
    processing_log = fields.Text(help="Log línea-a-línea de cada XML procesado o rechazado.")
    created_move_ids = fields.Many2many(
        comodel_name="account.move",
        relation="l10n_pe_inbox_msg_move_rel",
        string="Borradores creados",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    # ─── Mail alias: override message_new ──────────────────────────────

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Crea la inbox message + procesa attachments XML del email entrante."""
        defaults = {
            "name": msg_dict.get("subject") or _("Email sin asunto"),
            "email_from": msg_dict.get("from") or msg_dict.get("email_from"),
            "subject": msg_dict.get("subject"),
            "state": "draft",
        }
        if custom_values:
            defaults.update(custom_values)
        record = super().message_new(msg_dict, custom_values=defaults)
        record._process_email_attachments()
        return record

    # ─── Procesamiento de attachments ──────────────────────────────────

    def _process_email_attachments(self):
        """Itera ir.attachment del mensaje y procesa cada XML encontrado."""
        self.ensure_one()
        # Las attachments del email entrante quedan vinculadas al record vía
        # mail.thread; las buscamos por res_model + res_id.
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ]
        )
        if not attachments:
            self._log("No se encontraron attachments en el email.")
            self.state = "error"
            return

        payloads = extract_xml_payloads(attachments)
        if not payloads:
            self._log("Ningún attachment es XML válido (ni XML dentro de ZIP).")
            self.state = "error"
            return

        moves = self.env["account.move"]
        errors = 0
        for filename, xml_bytes in payloads:
            try:
                move = process_xml_bytes(
                    self.env,
                    xml_bytes,
                    xml_filename=filename,
                    auto_create_partner=True,
                )
            except Exception as exc:
                errors += 1
                self._log(f"❌ {filename}: {exc}")
                _logger.warning(
                    "partner_inbox: fallo procesando %s (msg %s): %s",
                    filename,
                    self.id,
                    exc,
                )
                continue
            moves |= move
            self._log(f"✓ {filename} → account.move borrador {move.id} ({move.ref or '-'})")

        self.created_move_ids = [(6, 0, moves.ids)]
        if errors and not moves:
            self.state = "error"
        elif errors:
            self.state = "error"  # cualquier fallo → marca error para revisión
        else:
            self.state = "processed"

    def _log(self, text: str):
        existing = self.processing_log or ""
        self.processing_log = f"{existing}{text}\n" if existing else f"{text}\n"
