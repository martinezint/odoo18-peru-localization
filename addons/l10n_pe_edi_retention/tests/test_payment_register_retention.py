# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_edi_retention")
class TestPaymentRegisterRetention(TransactionCase):
    """account.payment.register extendido: cálculo automático de retención IGV."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Retention",
                "country_id": cls.pe.id,
                "vat": "20131312955",
                "l10n_pe_retention_threshold": 700.0,
                "l10n_pe_retention_rate": 3.0,
                "l10n_pe_retention_serie": "R001",
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.env = cls.env(user=cls.env.user.with_company(cls.company))

        cls.partner_sujeto = cls.env["res.partner"].create(
            {
                "name": "Proveedor Sujeto Retención",
                "country_id": cls.pe.id,
                "vat": "20100047218",
                "l10n_pe_retention_applies": True,
                "supplier_rank": 1,
            }
        )
        cls.partner_no_sujeto = cls.env["res.partner"].create(
            {
                "name": "Proveedor Normal",
                "country_id": cls.pe.id,
                "vat": "20100047226",
                "l10n_pe_retention_applies": False,
                "supplier_rank": 1,
            }
        )

    def _create_posted_bill(self, partner, amount: float):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 5, 10),
                "date": date(2026, 5, 10),
                "ref": f"F-AUTO-{amount:.0f}",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Item",
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [],
                        },
                    )
                ],
            }
        )
        # Bypass validaciones latam: posteamos por SQL como hacen los otros tests
        self.env.cr.execute("UPDATE account_move SET state='posted' WHERE id=%s", (move.id,))
        self.env.cr.execute(
            "UPDATE account_move_line SET parent_state='posted' WHERE move_id=%s",
            (move.id,),
        )
        move.invalidate_recordset()
        return move

    def _make_register_wizard(self, move):
        return (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=move.ids)
            .create({})
        )

    # ─── Cálculo aplicabilidad + monto ────────────────────────────────

    def test_not_applicable_when_partner_not_flagged(self):
        bill = self._create_posted_bill(self.partner_no_sujeto, 1000.0)
        wiz = self._make_register_wizard(bill)
        self.assertFalse(wiz.l10n_pe_retention_applicable)
        self.assertEqual(wiz.l10n_pe_retention_amount, 0.0)

    def test_not_applicable_below_threshold(self):
        bill = self._create_posted_bill(self.partner_sujeto, 500.0)
        wiz = self._make_register_wizard(bill)
        self.assertFalse(wiz.l10n_pe_retention_applicable)

    def test_applicable_above_threshold(self):
        bill = self._create_posted_bill(self.partner_sujeto, 1000.0)
        wiz = self._make_register_wizard(bill)
        self.assertTrue(wiz.l10n_pe_retention_applicable)
        # 3% de 1000 = 30
        self.assertAlmostEqual(wiz.l10n_pe_retention_amount, 30.0, places=2)
        self.assertAlmostEqual(wiz.l10n_pe_retention_base, 1000.0, places=2)

    def test_applicable_at_exact_threshold_is_false(self):
        """SUNAT: solo > 700, no >=. 700 exacto NO se retiene."""
        bill = self._create_posted_bill(self.partner_sujeto, 700.0)
        wiz = self._make_register_wizard(bill)
        self.assertFalse(wiz.l10n_pe_retention_applicable)

    def test_custom_company_rate(self):
        """Si la empresa cambia la tasa (% ret), el cálculo lo refleja."""
        self.company.l10n_pe_retention_rate = 6.0  # ficticio para test
        bill = self._create_posted_bill(self.partner_sujeto, 1000.0)
        wiz = self._make_register_wizard(bill)
        self.assertAlmostEqual(wiz.l10n_pe_retention_amount, 60.0, places=2)

    # ─── Creación del comprobante de retención al confirmar pago ──────

    def test_create_payments_generates_retention_draft(self):
        bill = self._create_posted_bill(self.partner_sujeto, 1000.0)
        wiz = self._make_register_wizard(bill)
        wiz.action_create_payments()

        retentions = self.env["l10n.pe.retention"].search(
            [("company_id", "=", self.company.id), ("partner_id", "=", self.partner_sujeto.id)]
        )
        self.assertEqual(len(retentions), 1)
        ret = retentions
        self.assertEqual(ret.state, "draft")
        self.assertEqual(ret.name, "R001-1")
        self.assertEqual(len(ret.line_ids), 1)
        self.assertAlmostEqual(ret.line_ids[0].retention_amount, 30.0, places=2)

    def test_create_payments_no_retention_when_not_applicable(self):
        bill = self._create_posted_bill(self.partner_no_sujeto, 1000.0)
        wiz = self._make_register_wizard(bill)
        wiz.action_create_payments()

        retentions = self.env["l10n.pe.retention"].search(
            [("company_id", "=", self.company.id), ("partner_id", "=", self.partner_no_sujeto.id)]
        )
        self.assertFalse(retentions)

    def test_serie_counter_increments(self):
        """El correlativo R001-N se incrementa por cada nueva retención."""
        b1 = self._create_posted_bill(self.partner_sujeto, 1000.0)
        b2 = self._create_posted_bill(self.partner_sujeto, 2000.0)
        self._make_register_wizard(b1).action_create_payments()
        self._make_register_wizard(b2).action_create_payments()
        names = (
            self.env["l10n.pe.retention"]
            .search([("company_id", "=", self.company.id)], order="id")
            .mapped("name")
        )
        self.assertEqual(names, ["R001-1", "R001-2"])
