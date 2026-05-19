# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_double_entry_6_9")
class TestDoubleEntry(TransactionCase):
    """Doble apunte PCGE clase 6 ↔ clase 9 (vía 79)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Doble Apunte",
                "country_id": cls.pe.id,
                "vat": "20131312955",
                "l10n_pe_auto_double_entry": False,  # manual en tests
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.env = cls.env(user=cls.env.user.with_company(cls.company))

        # Localizamos cuentas del chart cargado
        Account = cls.env["account.account"]
        cls.acc_6 = Account.search(
            [("code", "=like", "6%"), ("company_ids", "in", cls.company.id)], limit=1
        )
        cls.acc_9_admin = Account.search(
            [("code", "=like", "94%"), ("company_ids", "in", cls.company.id)], limit=1
        )
        cls.acc_79 = Account.search(
            [("code", "=like", "79%"), ("company_ids", "in", cls.company.id)], limit=1
        )
        # Cuenta proveedor (clase 42)
        cls.acc_42 = Account.search(
            [("code", "=like", "42%"), ("company_ids", "in", cls.company.id)], limit=1
        )

        # Configura empresa con las cuentas destino
        if cls.acc_9_admin:
            cls.company.l10n_pe_dest_admin_account_id = cls.acc_9_admin.id
        if cls.acc_79:
            cls.company.l10n_pe_transfer_account_id = cls.acc_79.id
        cls.company.l10n_pe_default_destination_type = "admin"

    def _has_pcge_classes_6_9_79(self):
        return bool(self.acc_6 and self.acc_9_admin and self.acc_79 and self.acc_42)

    def _create_gasto_move(self, amount=1000.0):
        """Asiento manual: Debe 6x / Haber 42x (proveedor)."""
        return self.env["account.move"].create(
            {
                "move_type": "entry",
                "company_id": self.company.id,
                "date": date(2026, 5, 10),
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.acc_6.id,
                            "debit": amount,
                            "credit": 0.0,
                            "name": "Compra mercadería",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.acc_42.id,
                            "debit": 0.0,
                            "credit": amount,
                            "name": "Proveedor",
                        },
                    ),
                ],
            }
        )

    # ─── Cómputo necesidad ────────────────────────────────────────────

    def test_class_6_total_detected(self):
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        move = self._create_gasto_move(amount=500.0)
        self.assertAlmostEqual(move._l10n_pe_get_class_6_total(), 500.0)

    def test_needs_double_entry_true_when_class_6_present(self):
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        move = self._create_gasto_move()
        move.invalidate_recordset()
        self.assertTrue(move.l10n_pe_needs_double_entry)

    def test_needs_double_entry_false_after_generation(self):
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        move = self._create_gasto_move()
        move.action_l10n_pe_generate_double_entry()
        move.invalidate_recordset()
        self.assertFalse(move.l10n_pe_needs_double_entry)

    # ─── Generación correcta ──────────────────────────────────────────

    def test_generate_creates_counterpart_with_correct_amount(self):
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        move = self._create_gasto_move(amount=1500.0)
        move.action_l10n_pe_generate_double_entry()
        cp = move.l10n_pe_double_entry_move_id
        self.assertTrue(cp)
        self.assertEqual(len(cp.line_ids), 2)
        # Debit total = 1500 en clase 9
        debit_9 = sum(ln.debit for ln in cp.line_ids if ln.account_id.code.startswith("9"))
        credit_79 = sum(ln.credit for ln in cp.line_ids if ln.account_id.code.startswith("79"))
        self.assertAlmostEqual(debit_9, 1500.0)
        self.assertAlmostEqual(credit_79, 1500.0)

    def test_generate_uses_correct_destination_account(self):
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        move = self._create_gasto_move()
        move.l10n_pe_destination_type = "admin"
        move.action_l10n_pe_generate_double_entry()
        cp = move.l10n_pe_double_entry_move_id
        dest_line = cp.line_ids.filtered(lambda ln: ln.debit > 0)
        self.assertEqual(dest_line.account_id.id, self.acc_9_admin.id)

    # ─── Idempotencia ────────────────────────────────────────────────

    def test_generate_is_idempotent(self):
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        move = self._create_gasto_move()
        move.action_l10n_pe_generate_double_entry()
        first_cp = move.l10n_pe_double_entry_move_id
        move.action_l10n_pe_generate_double_entry()
        second_cp = move.l10n_pe_double_entry_move_id
        self.assertEqual(first_cp.id, second_cp.id)

    # ─── Manual override de cuenta ───────────────────────────────────

    def test_manual_destination_account_override(self):
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        # Buscamos otra cuenta 9x distinta (ej 95 Ventas)
        Account = self.env["account.account"]
        acc_95 = Account.search(
            [("code", "=like", "95%"), ("company_ids", "in", self.company.id)], limit=1
        )
        if not acc_95:
            self.skipTest("Chart PE no expone cta 95")
        move = self._create_gasto_move()
        move.write(
            {
                "l10n_pe_destination_type": "manual",
                "l10n_pe_destination_account_id": acc_95.id,
            }
        )
        move.action_l10n_pe_generate_double_entry()
        cp = move.l10n_pe_double_entry_move_id
        dest_line = cp.line_ids.filtered(lambda ln: ln.debit > 0)
        self.assertEqual(dest_line.account_id.id, acc_95.id)

    # ─── Configuración faltante ──────────────────────────────────────

    def test_missing_config_raises_when_button_pressed(self):
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        # Limpiamos la config para forzar el error
        self.company.l10n_pe_transfer_account_id = False
        move = self._create_gasto_move()
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            move.action_l10n_pe_generate_double_entry()

    def test_missing_config_silent_on_auto_post(self):
        """En modo auto (_post), si falta config NO debe romper el posting."""
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        self.company.l10n_pe_transfer_account_id = False
        move = self._create_gasto_move()
        # No debería lanzar — solo warning
        result = move._l10n_pe_generate_double_entry(raise_on_missing=False)
        self.assertFalse(result)

    # ─── No genera para moves sin clase 6 ────────────────────────────

    def test_no_generation_when_no_class_6(self):
        if not self._has_pcge_classes_6_9_79():
            self.skipTest("Chart PE no expone clases 6/9/79")
        # Asiento solo con cuentas de balance (1 y 4)
        Account = self.env["account.account"]
        acc_1 = Account.search(
            [("code", "=like", "1%"), ("company_ids", "in", self.company.id)], limit=1
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "company_id": self.company.id,
                "date": date(2026, 5, 10),
                "line_ids": [
                    (0, 0, {"account_id": acc_1.id, "debit": 100.0, "credit": 0.0, "name": "D"}),
                    (
                        0,
                        0,
                        {"account_id": self.acc_42.id, "debit": 0.0, "credit": 100.0, "name": "C"},
                    ),
                ],
            }
        )
        result = move._l10n_pe_generate_double_entry(raise_on_missing=False)
        self.assertFalse(result)
        self.assertFalse(move.l10n_pe_double_entry_move_id)


@tagged("post_install", "-at_install", "l10n_pe_double_entry_6_9")
class TestBatchWizard(TransactionCase):
    """Wizard masivo para regularizar pendientes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE Batch Doble",
                "country_id": cls.pe.id,
                "vat": "20131312955",
                "l10n_pe_auto_double_entry": False,
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.env = cls.env(user=cls.env.user.with_company(cls.company))

    def test_wizard_runs_without_error(self):
        """Verifica que el wizard se ejecuta sin moves a procesar."""
        wiz = self.env["l10n.pe.double.entry.batch.wizard"].create(
            {
                "company_id": self.company.id,
                "date_from": date(2026, 1, 1),
                "date_to": date(2026, 12, 31),
            }
        )
        wiz.action_run()
        # Sin moves: 0 procesados
        self.assertEqual(wiz.processed_count, 0)
        self.assertEqual(wiz.generated_count, 0)
