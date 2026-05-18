# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_exchange_rate_sbs")
class TestCompanyUpdate(TransactionCase):
    """Flujo end-to-end: company._l10n_pe_update_sbs_rates → res.currency.rate.

    Mockea SbsScraper.fetch para no tocar red.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")
        # EUR puede venir inactiva en algunos installs; la activamos para la prueba.
        if not cls.eur.active:
            cls.eur.active = True
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Exchange",
                "country_id": cls.pe.id,
            }
        )
        cls.company.l10n_pe_sbs_currency_ids = [(6, 0, [cls.usd.id, cls.eur.id])]

    def _mock_sbs_data(self, when):
        return {
            "USD": {"compra": 3.745, "venta": 3.752, "fecha": when},
            "EUR": {"compra": 4.120, "venta": 4.180, "fecha": when},
        }

    def test_update_writes_rates(self):
        when = date(2026, 5, 15)
        with patch(
            "odoo.addons.l10n_pe_exchange_rate_sbs.services.sbs.SbsScraper.fetch",
            return_value=self._mock_sbs_data(when),
        ):
            updated = self.company._l10n_pe_update_sbs_rates(when)
        self.assertEqual(set(updated), {"USD", "EUR"})

        usd_rate = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", when),
            ]
        )
        self.assertTrue(usd_rate)
        # Odoo guarda 1 PEN = X USD (inverso de SBS); rate_type='venta' por defecto
        # SBS venta USD = 3.752 → rate = 1/3.752 ≈ 0.266525
        self.assertAlmostEqual(usd_rate.rate, 1.0 / 3.752, places=6)

    def test_update_idempotent(self):
        when = date(2026, 5, 15)
        with patch(
            "odoo.addons.l10n_pe_exchange_rate_sbs.services.sbs.SbsScraper.fetch",
            return_value=self._mock_sbs_data(when),
        ):
            self.company._l10n_pe_update_sbs_rates(when)
            # Segundo run: debe sobreescribir, no duplicar
            self.company._l10n_pe_update_sbs_rates(when)

        usd_rates = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", when),
            ]
        )
        self.assertEqual(len(usd_rates), 1, "Debe haber 1 sola rate por (currency, company, fecha)")

    def test_update_uses_compra_when_configured(self):
        self.company.l10n_pe_sbs_rate_type = "compra"
        when = date(2026, 5, 16)
        with patch(
            "odoo.addons.l10n_pe_exchange_rate_sbs.services.sbs.SbsScraper.fetch",
            return_value=self._mock_sbs_data(when),
        ):
            self.company._l10n_pe_update_sbs_rates(when)

        usd_rate = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", when),
            ],
            limit=1,
        )
        # SBS compra USD = 3.745 → rate = 1/3.745
        self.assertAlmostEqual(usd_rate.rate, 1.0 / 3.745, places=6)

    def test_update_empty_sbs_response_returns_empty_list(self):
        when = date(2026, 5, 16)  # weekend
        with patch(
            "odoo.addons.l10n_pe_exchange_rate_sbs.services.sbs.SbsScraper.fetch",
            return_value={},
        ):
            updated = self.company._l10n_pe_update_sbs_rates(when)
        self.assertEqual(updated, [])

    def test_manual_button_raises_when_no_data(self):
        with patch(
            "odoo.addons.l10n_pe_exchange_rate_sbs.services.sbs.SbsScraper.fetch",
            return_value={},
        ):
            with self.assertRaisesRegex(UserError, "fin de semana"):
                self.company.action_l10n_pe_update_sbs_rates()

    def test_cron_iterates_only_pe_companies_with_auto_update(self):
        # Empresa US (no PE): debería ser skip
        us = self.env.ref("base.us")
        us_co = self.env["res.company"].create(
            {
                "name": "US Co",
                "country_id": us.id,
                "l10n_pe_sbs_auto_update": True,
            }
        )
        call_companies = []

        def _track_call(self_company, when=None):
            call_companies.append(self_company.id)
            return []

        with patch(
            "odoo.addons.l10n_pe_exchange_rate_sbs.models.res_company.ResCompany."
            "_l10n_pe_update_sbs_rates",
            _track_call,
        ):
            self.env["res.company"]._cron_l10n_pe_update_sbs_rates()

        # La PE de test sí, la US no
        self.assertIn(self.company.id, call_companies)
        self.assertNotIn(us_co.id, call_companies)

    def test_company_with_auto_update_disabled_not_processed(self):
        self.company.l10n_pe_sbs_auto_update = False
        call_companies = []

        def _track_call(self_company, when=None):
            call_companies.append(self_company.id)
            return []

        with patch(
            "odoo.addons.l10n_pe_exchange_rate_sbs.models.res_company.ResCompany."
            "_l10n_pe_update_sbs_rates",
            _track_call,
        ):
            self.env["res.company"]._cron_l10n_pe_update_sbs_rates()

        self.assertNotIn(self.company.id, call_companies)
