# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.tests.common import TransactionCase, tagged

# Mapa de templates esperados → (amount, amount_type, type_tax_use, kind)
EXPECTED_TAXES = {
    "tax_ret_igv_1_5": (1.5, "percent", "purchase", "retencion_igv"),
    "tax_ret_igv_3": (3.0, "percent", "purchase", "retencion_igv"),
    "tax_ret_igv_6": (6.0, "percent", "purchase", "retencion_igv"),
    "tax_perc_igv_2": (2.0, "percent", "sale", "percepcion_igv"),
    "tax_icbper": (0.50, "fixed", "sale", "icbper"),
    "tax_ivap_4": (4.0, "percent", "sale", "ivap"),
}

EXPECTED_GROUPS = [
    "tax_group_ret_igv",
    "tax_group_perc_igv",
    "tax_group_icbper",
    "tax_group_ivap",
    "tax_group_isc_al_valor",
    "tax_group_isc_especifico",
    "tax_group_isc_al_valor_cigarrillos",
]


@tagged("post_install", "-at_install", "l10n_pe_taxes_extras")
class TestTaxesLoaded(TransactionCase):
    """Verifica que los tax groups e impuestos extras cargan en una empresa
    PE con chart 'pe' aplicado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.test_company = cls.env["res.company"].create({
            "name": "Test PE Co (taxes extras)",
            "country_id": cls.pe.id,
        })
        cls.env["account.chart.template"].try_loading(
            "pe", company=cls.test_company, install_demo=False
        )

    def _get_tax(self, template_id):
        xmlid = f"account.{self.test_company.id}_{template_id}"
        return self.env.ref(xmlid, raise_if_not_found=False)

    def _get_group(self, template_id):
        # Tax groups en Odoo 18 también usan prefijo company en su XML ID
        # (account.{co_id}_{tpl_id}), aunque los registros son shared entre
        # companies por país.
        xmlid = f"account.{self.test_company.id}_{template_id}"
        return self.env.ref(xmlid, raise_if_not_found=False)

    # ─── Tax Groups ──────────────────────────────────────────────────

    def test_all_tax_groups_created(self):
        for grp_id in EXPECTED_GROUPS:
            grp = self._get_group(grp_id)
            self.assertTrue(grp, f"Tax group {grp_id} no fue creado.")

    # ─── Impuestos ───────────────────────────────────────────────────

    def test_all_taxes_exist(self):
        for tpl_id in EXPECTED_TAXES:
            tax = self._get_tax(tpl_id)
            self.assertTrue(tax, f"Impuesto {tpl_id} no fue creado para la empresa.")

    def test_taxes_have_correct_amounts(self):
        for tpl_id, (amount, amount_type, type_tax_use, kind) in EXPECTED_TAXES.items():
            tax = self._get_tax(tpl_id)
            self.assertTrue(tax, f"Tax {tpl_id} missing")
            self.assertEqual(tax.amount, amount, f"{tpl_id} amount")
            self.assertEqual(tax.amount_type, amount_type, f"{tpl_id} amount_type")
            self.assertEqual(tax.type_tax_use, type_tax_use, f"{tpl_id} type_tax_use")
            self.assertEqual(tax.l10n_pe_tax_kind, kind, f"{tpl_id} l10n_pe_tax_kind")

    def test_retencion_6_inactive_by_default(self):
        """Tasa histórica de 6% se carga pero queda inactiva."""
        tax = self._get_tax("tax_ret_igv_6")
        self.assertTrue(tax)
        self.assertFalse(
            tax.active,
            "Retención 6% (histórica) debería cargarse inactiva por defecto.",
        )

    def test_icbper_is_fixed_amount(self):
        tax = self._get_tax("tax_icbper")
        self.assertTrue(tax)
        self.assertEqual(tax.amount_type, "fixed")
        self.assertEqual(tax.amount, 0.50)

    def test_tax_kind_filter_works(self):
        """Verifica que el field l10n_pe_tax_kind permite filtrar correctamente.

        Usa active_test=False porque la retención del 6% se carga inactiva.
        """
        retenciones = self.env["account.tax"].with_context(active_test=False).search([
            ("l10n_pe_tax_kind", "=", "retencion_igv"),
            ("company_id", "=", self.test_company.id),
        ])
        self.assertEqual(
            len(retenciones), 3,
            "Deberían existir 3 retenciones (1.5/3/6%) en la empresa, "
            f"se encontraron {len(retenciones)}",
        )

    def test_active_retencion_count(self):
        """Solo 2 retenciones activas por defecto (1.5 y 3%); la del 6% es histórica."""
        active_ret = self.env["account.tax"].search([
            ("l10n_pe_tax_kind", "=", "retencion_igv"),
            ("company_id", "=", self.test_company.id),
        ])
        self.assertEqual(len(active_ret), 2)
