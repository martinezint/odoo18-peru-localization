# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.tests.common import TransactionCase, tagged

from ..hooks import _l10n_pe_coa_post_init


@tagged("post_install", "-at_install", "l10n_pe_coa_pcge2019")
class TestPostInitHook(TransactionCase):
    """Unit tests del hook _l10n_pe_coa_post_init.

    Crea empresas frescas para no contaminar el estado de la company principal
    del entorno de tests.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.us = cls.env.ref("base.us")

    def _new_pe_company(self, name):
        return self.env["res.company"].create({
            "name": name,
            "country_id": self.pe.id,
        })

    def test_hook_applies_chart_to_fresh_pe_company(self):
        co = self._new_pe_company("PE Fresh Co")
        self.assertFalse(co.chart_template, "Empresa nueva no debe tener chart aún.")
        _l10n_pe_coa_post_init(self.env)
        co.invalidate_recordset()
        self.assertEqual(co.chart_template, "pe",
                         "Hook debió aplicar chart 'pe' a la empresa peruana sin chart.")

    def test_hook_skips_company_with_chart_already(self):
        co = self._new_pe_company("PE Co with chart")
        self.env["account.chart.template"].try_loading(
            "pe", company=co, install_demo=False
        )
        co.invalidate_recordset()
        self.assertEqual(co.chart_template, "pe")
        # Re-ejecutar no debe romper
        _l10n_pe_coa_post_init(self.env)
        co.invalidate_recordset()
        self.assertEqual(co.chart_template, "pe")

    def test_hook_skips_non_pe_company(self):
        co = self.env["res.company"].create({
            "name": "US Co",
            "country_id": self.us.id,
        })
        _l10n_pe_coa_post_init(self.env)
        co.invalidate_recordset()
        # No debe haber aplicado chart 'pe' a una empresa de EEUU
        self.assertNotEqual(co.chart_template, "pe")

    def test_hook_does_not_raise_when_no_pe_companies(self):
        """Si no hay empresas peruanas, el hook simplemente loggea y retorna."""
        # No tocamos data; solo verificamos que llamarlo en cualquier estado del
        # entorno (con o sin empresas PE) no levanta excepción.
        try:
            _l10n_pe_coa_post_init(self.env)
        except Exception as exc:
            self.fail(f"_l10n_pe_coa_post_init no debe levantar: {exc}")
