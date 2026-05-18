# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models

# Umbral SUNAT: detracciones aplican solo a operaciones cuyo importe total
# (incluyendo IGV) excede S/ 700.00.
DETRACCION_MIN_AMOUNT = 700.0


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_pe_detraccion_code_id = fields.Many2one(
        comodel_name="l10n.pe.detraccion.code",
        string="Código de Detracción",
        compute="_compute_l10n_pe_detraccion",
        store=True,
        readonly=False,
        help="Tomado del producto principal de la factura. Editable manualmente "
             "si la factura tiene productos con códigos distintos.",
    )
    l10n_pe_detraccion_amount = fields.Monetary(
        string="Monto Detracción",
        compute="_compute_l10n_pe_detraccion",
        store=True,
        currency_field="currency_id",
        help="Calculado como % del total. Solo aplica si total > S/700 según R.S. SUNAT.",
    )
    l10n_pe_detraccion_has_application = fields.Boolean(
        string="Sujeto a Detracción",
        compute="_compute_l10n_pe_detraccion",
        store=True,
        help="True si el código está asignado y el total supera el umbral.",
    )
    l10n_pe_detraccion_constancia = fields.Char(
        string="N° Constancia Depósito",
        copy=False,
        help="Número de la constancia de depósito en el Banco de la Nación. "
             "Imprescindible para usar el crédito fiscal del IGV.",
    )
    l10n_pe_detraccion_date = fields.Date(
        string="Fecha Depósito",
        copy=False,
        help="Fecha del depósito en el Banco de la Nación.",
    )

    # ─── Cálculo automático ────────────────────────────────────────────

    @api.depends("invoice_line_ids.product_id.l10n_pe_detraccion_code_id",
                 "amount_total", "move_type")
    def _compute_l10n_pe_detraccion(self):
        for move in self:
            # Solo aplica a facturas de compra (recibimos comprobantes con
            # detracción) y de venta (emitimos con leyenda de detracción).
            if move.move_type not in ("in_invoice", "in_refund", "out_invoice", "out_refund"):
                move.l10n_pe_detraccion_code_id = False
                move.l10n_pe_detraccion_amount = 0.0
                move.l10n_pe_detraccion_has_application = False
                continue

            # Toma el código del primer producto que tenga uno asignado.
            # Si la factura mezcla productos con códigos diferentes, el usuario
            # debe ajustar manualmente (escenario raro en operación real).
            code = False
            for line in move.invoice_line_ids:
                if line.product_id and line.product_id.l10n_pe_detraccion_code_id:
                    code = line.product_id.l10n_pe_detraccion_code_id
                    break

            move.l10n_pe_detraccion_code_id = code
            if code and move.amount_total > DETRACCION_MIN_AMOUNT:
                move.l10n_pe_detraccion_amount = (
                    move.amount_total * code.percentage / 100.0
                )
                move.l10n_pe_detraccion_has_application = True
            else:
                move.l10n_pe_detraccion_amount = 0.0
                move.l10n_pe_detraccion_has_application = False

    # ─── Validación al postear ─────────────────────────────────────────

    def _post(self, soft=True):
        """Warning (no bloqueo) si se postea una factura con detracción sin constancia.

        Razonamiento: en el flujo real, la constancia llega DESPUÉS del pago,
        no al posteo. Por eso no bloqueamos; solo loggeamos chatter para que
        contabilidad lo persiga.
        """
        result = super()._post(soft=soft)
        for move in self:
            if (move.l10n_pe_detraccion_has_application
                    and not move.l10n_pe_detraccion_constancia
                    and move.move_type in ("in_invoice", "in_refund")):
                move.message_post(body=_(
                    "⚠️ Esta factura está sujeta a detracción (%(code)s, %(amount)s %(curr)s) "
                    "y aún no tiene número de constancia de depósito. "
                    "Recuerda registrar la constancia al efectuar el pago en el "
                    "Banco de la Nación para poder usar el crédito fiscal del IGV.",
                    code=move.l10n_pe_detraccion_code_id.display_name,
                    amount=move.l10n_pe_detraccion_amount,
                    curr=move.currency_id.symbol,
                ))
        return result
