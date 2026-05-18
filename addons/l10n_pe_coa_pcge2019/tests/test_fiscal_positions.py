# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.tests.common import TransactionCase, tagged

# Templates XML IDs cargados desde nuestro CSV en data/template/
FP_TEMPLATE_IDS = {
    "fp_pe_general": "general",
    "fp_pe_mype": "mype",
    "fp_pe_rer": "rer",
    "fp_pe_nrus": "nrus",
}


@tagged("post_install", "-at_install", "l10n_pe_coa_pcge2019")
class TestFiscalPositionsPerRegimen(TransactionCase):
    """Verifica que tras aplicar chart 'pe' a una empresa peruana, las 4
    posiciones fiscales por régimen quedan creadas y vinculadas correctamente."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.test_company = cls.env["res.company"].create(
            {
                "name": "Test PE Co (FP tests)",
                "country_id": cls.pe.id,
            }
        )
        cls.env["account.chart.template"].try_loading(
            "pe", company=cls.test_company, install_demo=False
        )

    def _get_fp(self, template_xmlid):
        """Localiza la posición fiscal creada para la empresa de prueba.

        Odoo 18 crea el XML ID company-específico como ``account.{company_id}_{template_id}``.
        """
        xmlid = f"account.{self.test_company.id}_{template_xmlid}"
        return self.env.ref(xmlid, raise_if_not_found=False)

    def test_all_4_fiscal_positions_exist(self):
        for tpl_id in FP_TEMPLATE_IDS:
            fp = self._get_fp(tpl_id)
            self.assertTrue(
                fp,
                f"Falta posición fiscal {tpl_id} en empresa {self.test_company.name}",
            )

    def test_fiscal_positions_have_correct_regimen(self):
        for tpl_id, expected_regimen in FP_TEMPLATE_IDS.items():
            fp = self._get_fp(tpl_id)
            self.assertTrue(fp, f"FP {tpl_id} no encontrada")
            self.assertEqual(
                fp.l10n_pe_regimen_tributario,
                expected_regimen,
                f"FP {tpl_id} debería tener régimen={expected_regimen}, "
                f"tiene {fp.l10n_pe_regimen_tributario}",
            )

    def test_fiscal_positions_country_is_peru(self):
        for tpl_id in FP_TEMPLATE_IDS:
            fp = self._get_fp(tpl_id)
            if not fp:
                continue
            self.assertEqual(fp.country_id, self.pe)

    def test_fiscal_positions_belong_to_test_company(self):
        for tpl_id in FP_TEMPLATE_IDS:
            fp = self._get_fp(tpl_id)
            if not fp:
                continue
            self.assertEqual(fp.company_id, self.test_company)

    def test_pcge_extra_accounts_loaded(self):
        """Verifica que las cuentas extras del PCGE (elemento 9) fueron creadas
        cuando se aplicó el chart 'pe' (nuestro CSV se mergeó con el de core).

        En Odoo 18 account.account.code es ``code_store`` (JSONB indexed por
        company). Buscamos por el XML ID company-específico, que es el contrato
        del loader del chart template.
        """
        co_id = self.test_company.id
        for tpl_id in ("chart_pcge_9111", "chart_pcge_9211", "chart_pcge_9911"):
            xmlid = f"account.{co_id}_{tpl_id}"
            acc = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(
                acc,
                f"Cuenta extra PCGE {tpl_id} no fue creada para la empresa "
                f"{self.test_company.name} (XML ID esperado: {xmlid})",
            )
