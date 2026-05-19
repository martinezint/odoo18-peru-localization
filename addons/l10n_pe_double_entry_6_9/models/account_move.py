# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Doble apunte PCGE clase 6 ↔ clase 9 (vía 79).

Cuando un asiento contiene líneas en cuentas de gastos por naturaleza
(clase 6), SUNAT obliga a generar adicionalmente el asiento por función
(clase 9), equilibrado por la cuenta puente 79.

Patrón de asientos:

  Original (gasto por naturaleza):
    Debe 60xxxx Compras ...........  1000
    Debe 40xxxx IGV crédito fiscal    180
      Haber 42xxxx Cuentas por pagar      1180

  Generado por este módulo (gasto por función):
    Debe 94xxxx Gastos administración   1000
      Haber 79xxxx Cargas imputables       1000

La suma "Debe clase 9" = "Haber clase 79" = "Debe clase 6 del original".
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


DESTINATION_TYPE_TO_FIELD = {
    "admin": "l10n_pe_dest_admin_account_id",
    "sales": "l10n_pe_dest_sales_account_id",
    "production": "l10n_pe_dest_production_account_id",
    "distribution": "l10n_pe_dest_distribution_account_id",
}


class AccountMove(models.Model):
    _inherit = "account.move"

    # ─── Configuración del doble apunte para este move ────────────────
    l10n_pe_destination_type = fields.Selection(
        selection=[
            ("admin", "Administración (94)"),
            ("sales", "Ventas (95)"),
            ("production", "Producción (92)"),
            ("distribution", "Distribución (93)"),
            ("manual", "Manual (override cuenta)"),
        ],
        string="Función destino (cls 9)",
        help="Función a la que se imputará el gasto en el asiento contrapartida de clase 9.",
    )
    l10n_pe_destination_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta destino clase 9",
        help="Si está vacío, se usa la cuenta destino configurada en la "
        "empresa según l10n_pe_destination_type.",
        domain="[('code', '=like', '9%')]",
    )

    # ─── Vínculo con el move contrapartida generado ───────────────────
    l10n_pe_double_entry_move_id = fields.Many2one(
        comodel_name="account.move",
        string="Asiento doble apunte (9↔79)",
        readonly=True,
        copy=False,
        help="Asiento generado automáticamente con la contrapartida en clase 9.",
    )
    l10n_pe_double_entry_origin_id = fields.Many2one(
        comodel_name="account.move",
        string="Asiento origen (gasto por naturaleza)",
        readonly=True,
        copy=False,
    )

    l10n_pe_needs_double_entry = fields.Boolean(
        string="Necesita doble apunte",
        compute="_compute_l10n_pe_needs_double_entry",
        store=False,
    )

    # ─── Cómputo ──────────────────────────────────────────────────────

    @api.depends(
        "line_ids.account_id", "l10n_pe_double_entry_move_id", "l10n_pe_double_entry_origin_id"
    )
    def _compute_l10n_pe_needs_double_entry(self):
        for move in self:
            if move.l10n_pe_double_entry_move_id or move.l10n_pe_double_entry_origin_id:
                move.l10n_pe_needs_double_entry = False
                continue
            move.l10n_pe_needs_double_entry = bool(move._l10n_pe_get_class_6_total() > 0)

    def _l10n_pe_get_class_6_total(self) -> float:
        """Suma del debe de las líneas con cuenta de clase 6."""
        self.ensure_one()
        total = 0.0
        for ln in self.line_ids:
            code = (ln.account_id.code or "").strip()
            if code.startswith("6"):
                total += ln.debit
        return total

    # ─── Resolución de cuenta destino ─────────────────────────────────

    def _l10n_pe_resolve_destination_account(self):
        """Devuelve la cuenta 9x destino a usar en el contrapartida."""
        self.ensure_one()
        if self.l10n_pe_destination_account_id:
            return self.l10n_pe_destination_account_id
        company = self.company_id
        dest_type = self.l10n_pe_destination_type or company.l10n_pe_default_destination_type
        if not dest_type or dest_type == "manual":
            return self.env["account.account"]
        field_name = DESTINATION_TYPE_TO_FIELD.get(dest_type)
        if not field_name:
            return self.env["account.account"]
        return getattr(company, field_name)

    # ─── Generación del doble apunte ──────────────────────────────────

    def action_l10n_pe_generate_double_entry(self):
        """Acción de botón: genera el doble apunte para este move."""
        for move in self:
            move._l10n_pe_generate_double_entry(raise_on_missing=True)
        return True

    def _l10n_pe_generate_double_entry(self, raise_on_missing: bool = False):
        """Crea el asiento contrapartida en clase 9 + 79.

        Args:
            raise_on_missing: si True, lanza UserError cuando falta config.
                Si False, solo loggea (uso desde _post() automático).

        Returns:
            account.move generado, o False si no aplica/falla silenciosamente.
        """
        self.ensure_one()
        if self.l10n_pe_double_entry_move_id:
            # Ya tiene contrapartida → idempotente
            return self.l10n_pe_double_entry_move_id
        if self.l10n_pe_double_entry_origin_id:
            # Este move ES la contrapartida de otro → no generar
            return False

        amount = self._l10n_pe_get_class_6_total()
        if amount <= 0:
            return False

        company = self.company_id
        dest_account = self._l10n_pe_resolve_destination_account()
        transfer_account = company.l10n_pe_transfer_account_id

        if not dest_account or not transfer_account:
            msg = _(
                "Doble apunte PE no generado para %(move)s: falta configuración. "
                "Cta destino 9x: %(dest)s, Cta 79: %(transfer)s."
            ) % {
                "move": self.display_name,
                "dest": dest_account.code if dest_account else "MISSING",
                "transfer": transfer_account.code if transfer_account else "MISSING",
            }
            if raise_on_missing:
                raise UserError(msg)
            _logger.warning(msg)
            return False

        # Reusamos el diario del move original si es general; si no, buscamos uno
        journal = self._l10n_pe_find_double_entry_journal()
        if not journal:
            msg = _("No se encontró diario tipo 'general' para empresa %s") % company.name
            if raise_on_missing:
                raise UserError(msg)
            _logger.warning(msg)
            return False

        partner_id = self.partner_id.id if self.partner_id else False
        counterpart = (
            self.env["account.move"]
            .with_company(company)
            .create(
                {
                    "move_type": "entry",
                    "journal_id": journal.id,
                    "company_id": company.id,
                    "date": self.date,
                    "ref": _("Doble apunte 9↔79 de %s") % (self.name or self.ref or self.id),
                    "l10n_pe_double_entry_origin_id": self.id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": dest_account.id,
                                "partner_id": partner_id,
                                "debit": amount,
                                "credit": 0.0,
                                "name": _("Imputación a %s") % dest_account.code,
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "account_id": transfer_account.id,
                                "partner_id": partner_id,
                                "debit": 0.0,
                                "credit": amount,
                                "name": _("Cargas imputables"),
                            },
                        ),
                    ],
                }
            )
        )
        # Posteamos automáticamente la contrapartida
        try:
            counterpart.action_post()
        except Exception:
            _logger.exception("Fallo posteando contrapartida 9↔79 para %s", self.display_name)

        self.l10n_pe_double_entry_move_id = counterpart.id
        # Mensaje en chatter
        self.message_post(
            body=_(
                "Generado doble apunte PE: <a href=# data-oe-model=account.move data-oe-id=%s>%s</a>"
            )
            % (counterpart.id, counterpart.name or counterpart.ref)
        )
        return counterpart

    def _l10n_pe_find_double_entry_journal(self):
        """Diario donde se contabiliza el contrapartida.
        Preferencia: diario tipo general de la empresa, primero el del move original
        si es general, si no el primero disponible."""
        self.ensure_one()
        if self.journal_id and self.journal_id.type == "general":
            return self.journal_id
        return self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company_id.id)],
            limit=1,
        )

    # ─── Hook _post: auto-generar al postear ─────────────────────────

    def _post(self, soft=True):
        """Override estándar de Odoo para inyectar el doble apunte automático."""
        posted = super()._post(soft=soft)
        for move in posted:
            company = move.company_id
            if not company.l10n_pe_auto_double_entry:
                continue
            # Evitar bucle: no auto-generar sobre el propio contrapartida
            if move.l10n_pe_double_entry_origin_id:
                continue
            if move.l10n_pe_double_entry_move_id:
                continue
            move._l10n_pe_generate_double_entry(raise_on_missing=False)
        return posted
