# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Extensión de account.payment.register para retenciones automáticas.

Cuando un contador hace "Registrar Pago" sobre una factura de proveedor
sujeto a retención IGV (`res.partner.l10n_pe_retention_applies` + factura
con monto > umbral configurado), el wizard:

  - Muestra el monto de retención calculado (config.rate% sobre subtotal sin IGV)
  - Permite ajustar/desactivar antes de confirmar
  - Al confirmar:
      1. Crea el `account.payment` con el monto neto (importe - retención)
      2. Crea un `l10n.pe.retention` borrador vinculado a las facturas pagadas
      3. Devuelve acción que abre el comprobante de retención generado

Diseño: NO postea automáticamente la retención. El contador la revisa,
añade glosa, y la postea (que dispara el flujo UBL+envío EDI).
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    l10n_pe_retention_applicable = fields.Boolean(
        string="Aplicar retención IGV",
        compute="_compute_l10n_pe_retention",
        store=True,
        readonly=False,
        help="Marca automáticamente si proveedor sujeto a retención + monto > umbral.",
    )
    l10n_pe_retention_amount = fields.Monetary(
        string="Monto retención",
        compute="_compute_l10n_pe_retention",
        store=True,
        readonly=False,
        currency_field="currency_id",
    )
    l10n_pe_retention_base = fields.Monetary(
        string="Base imponible",
        compute="_compute_l10n_pe_retention",
        store=True,
        currency_field="currency_id",
        help="Subtotal sin IGV de las facturas seleccionadas.",
    )

    # ─── Computed: aplicabilidad + monto ──────────────────────────────

    @api.depends("partner_id", "amount", "company_id", "line_ids")
    def _compute_l10n_pe_retention(self):
        for wizard in self:
            applicable, base, retention = wizard._l10n_pe_retention_calc()
            wizard.l10n_pe_retention_applicable = applicable
            wizard.l10n_pe_retention_base = base
            wizard.l10n_pe_retention_amount = retention

    def _l10n_pe_retention_calc(self) -> tuple[bool, float, float]:
        """Devuelve (aplica, base_sin_igv, monto_retencion)."""
        self.ensure_one()
        company = self.company_id or self.env.company
        partner = self.partner_id
        if not partner or not partner.l10n_pe_retention_applies:
            return False, 0.0, 0.0
        threshold = company.l10n_pe_retention_threshold or 0.0
        rate = company.l10n_pe_retention_rate or 0.0
        # Base: sumamos amount_untaxed de las facturas relacionadas (in_invoice)
        moves = self.line_ids.move_id.filtered(lambda m: m.move_type == "in_invoice")
        base = sum(moves.mapped("amount_untaxed"))
        total = sum(moves.mapped("amount_total"))
        if total <= threshold:
            return False, base, 0.0
        retention = round(base * (rate / 100.0), 2)
        return True, base, retention

    # ─── Override: crear retención al confirmar pago ─────────────────

    def _create_payments(self):
        """Tras crear el pago estándar, genera el comprobante de retención.

        Solo se ejecuta si `l10n_pe_retention_applicable` y `> 0`.
        El monto del pago Odoo NO se modifica aquí (queda el total bruto):
        la retención se contabilizará como un asiento separado al postear
        el `l10n.pe.retention`.
        """
        payments = super()._create_payments()
        for wizard in self:
            if not (wizard.l10n_pe_retention_applicable and wizard.l10n_pe_retention_amount > 0):
                continue
            try:
                wizard._l10n_pe_create_retention(payments)
            except Exception:
                _logger.exception("Fallo creando retención auto para wizard %s", wizard.id)
                # NO re-raise: el pago ya está creado; el contador hace la retención manual.
        return payments

    def _l10n_pe_create_retention(self, payments):
        """Crea un l10n.pe.retention borrador con las líneas de origen."""
        self.ensure_one()
        Retention = self.env["l10n.pe.retention"]
        moves = self.line_ids.move_id.filtered(lambda m: m.move_type == "in_invoice")
        if not moves:
            return False

        company = self.company_id or self.env.company
        serie = company.l10n_pe_retention_serie or "R001"
        # Correlativo: el siguiente número en la secuencia (lookup last)
        last = Retention.search(
            [
                ("company_id", "=", company.id),
                ("name", "=like", f"{serie}-%"),
            ],
            order="id desc",
            limit=1,
        )
        next_num = 1
        if last and "-" in last.name:
            try:
                next_num = int(last.name.split("-")[1]) + 1
            except (ValueError, IndexError):
                next_num = 1
        name = f"{serie}-{next_num}"

        # Líneas: una por factura. La base se reparte proporcional al amount_untaxed.
        rate = company.l10n_pe_retention_rate or 0.0
        line_vals = []
        for move in moves:
            base_move = move.amount_untaxed
            ret_move = round(base_move * (rate / 100.0), 2)
            line_vals.append(
                (
                    0,
                    0,
                    {
                        "doc_type_code": "01",
                        "doc_serie_number": move.name or move.ref or "SIN-NUM",
                        "doc_issue_date": move.invoice_date or fields.Date.today(),
                        "doc_total_amount": move.amount_total,
                        "paid_amount": move.amount_total,
                        "paid_date": self.payment_date,
                        "retention_amount": ret_move,
                        "retention_date": self.payment_date,
                    },
                )
            )

        retention = Retention.create(
            {
                "name": name,
                "issue_date": self.payment_date,
                "company_id": company.id,
                "partner_id": self.partner_id.id,
                "currency_id": self.currency_id.id,
                "regime_code": "01",
                "regime_percent": rate,
                "line_ids": line_vals,
            }
        )
        # Vínculo de auditoría: anota en el chatter del pago
        for payment in payments:
            payment.message_post(
                body=_(
                    "Generado comprobante de retención borrador: "
                    "<a href=# data-oe-model=l10n.pe.retention "
                    "data-oe-id=%(id)s>%(name)s</a>"
                )
                % {"id": retention.id, "name": retention.name},
            )
        return retention
