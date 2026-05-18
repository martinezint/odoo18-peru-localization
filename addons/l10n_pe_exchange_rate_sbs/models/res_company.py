# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.sbs import SbsScraper

_logger = logging.getLogger(__name__)


SBS_RATE_TYPE_SELECTION = [
    ("compra", "Compra"),
    ("venta", "Venta"),
]


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_pe_sbs_auto_update = fields.Boolean(
        string="Auto-actualizar T/C desde SBS",
        default=True,
        help="Si está activado, el cron diario actualizará los tipos de cambio "
        "de las monedas seleccionadas usando la SBS como fuente.",
    )
    l10n_pe_sbs_rate_type = fields.Selection(
        selection=SBS_RATE_TYPE_SELECTION,
        string="Tipo de cambio a usar",
        default="venta",
        help="SBS publica compra y venta diarios. Para contabilidad y SUNAT "
        "se usa típicamente el tipo VENTA.",
    )
    l10n_pe_sbs_currency_ids = fields.Many2many(
        "res.currency",
        "res_company_l10n_pe_sbs_currency_rel",
        "company_id",
        "currency_id",
        string="Monedas a actualizar",
        help="Monedas para las que se actualizará el tipo de cambio diariamente. "
        "Por defecto USD si no se especifica.",
    )

    # ─── Acción manual ─────────────────────────────────────────────────

    def action_l10n_pe_update_sbs_rates(self):
        """Botón: actualiza tipos de cambio AHORA contra SBS para esta empresa."""
        self.ensure_one()
        updated = self._l10n_pe_update_sbs_rates(when=date.today())
        if not updated:
            raise UserError(
                _(
                    "SBS no devolvió tipos de cambio para hoy. Suele significar "
                    "que es fin de semana o feriado, o que SBS aún no ha publicado. "
                    "Intenta de nuevo más tarde."
                )
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Tipos de cambio actualizados"),
                "message": _("Se actualizaron %d monedas desde SBS.") % len(updated),
                "type": "success",
                "sticky": False,
            },
        }

    # ─── Cron y lógica de update ───────────────────────────────────────

    @api.model
    def _cron_l10n_pe_update_sbs_rates(self):
        """Entry point del cron diario. Itera empresas con auto-update activado.

        Errores en una empresa no detienen el procesamiento de las siguientes.
        """
        companies = self.search(
            [
                ("partner_id.country_id.code", "=", "PE"),
                ("l10n_pe_sbs_auto_update", "=", True),
            ]
        )
        if not companies:
            _logger.info("l10n_pe_exchange_rate_sbs: no hay empresas PE con auto-update activo.")
            return

        for company in companies:
            try:
                company._l10n_pe_update_sbs_rates(when=date.today())
            except Exception:
                _logger.exception("Fallo actualizando T/C desde SBS para empresa %s", company.name)

    def _l10n_pe_update_sbs_rates(self, when: date) -> list[str]:
        """Hace el fetch SBS y escribe las rates. Devuelve lista de ISO actualizadas.

        Idempotente para una misma fecha: si la rate ya existe, la sobreescribe.
        """
        self.ensure_one()
        # res.currency tiene active=True por defecto pero muchas vienen inactivas
        # (EUR, GBP, JPY...). Si el admin las añadió a la m2m queremos respetar
        # esa intención y no filtrarlas — el active_test las escondería.
        currencies = (
            self.with_context(active_test=False).l10n_pe_sbs_currency_ids
            or self._default_sbs_currencies()
        )
        if not currencies:
            _logger.info("Empresa %s: sin monedas SBS configuradas, skip.", self.name)
            return []

        scraper = SbsScraper()
        sbs_data = scraper.fetch(when)
        if not sbs_data:
            _logger.info(
                "SBS no devolvió data para %s (fecha %s). Puede ser fin de semana o feriado.",
                self.name,
                when,
            )
            return []

        rate_field = self.l10n_pe_sbs_rate_type or "venta"
        updated = []
        Rate = self.env["res.currency.rate"]

        for currency in currencies:
            iso = currency.name
            data = sbs_data.get(iso)
            if not data:
                _logger.warning(
                    "SBS: %s no aparece en la respuesta para %s.",
                    iso,
                    when,
                )
                continue
            sbs_rate = data[rate_field]
            # Odoo guarda rates como inverso: 1 PEN = X currency.
            # SBS publica 1 USD = X PEN, así que invertimos.
            inverted_rate = 1.0 / sbs_rate if sbs_rate else 0.0
            existing = Rate.search(
                [
                    ("name", "=", when),
                    ("currency_id", "=", currency.id),
                    ("company_id", "=", self.id),
                ],
                limit=1,
            )
            vals = {
                "name": when,
                "currency_id": currency.id,
                "company_id": self.id,
                "rate": inverted_rate,
            }
            if existing:
                existing.write(vals)
            else:
                Rate.create(vals)
            updated.append(iso)
            _logger.info(
                "SBS: actualizado %s para %s en %s = %s (inverso de %s)",
                iso,
                self.name,
                when,
                inverted_rate,
                sbs_rate,
            )
        return updated

    def _default_sbs_currencies(self):
        """USD por defecto si la empresa no configuró monedas."""
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        return usd if usd else self.env["res.currency"]
