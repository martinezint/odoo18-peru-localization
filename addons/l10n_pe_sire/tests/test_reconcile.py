# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date
from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from ..services.sire_proposal_parser import RceProposalLine


@tagged("post_install", "-at_install", "l10n_pe_sire")
class TestSireReconcile(TransactionCase):
    """Matcher de propuesta SUNAT → account.move."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test PE SIRE Reconcile",
                "country_id": cls.pe.id,
                "vat": "20131312955",
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.env = cls.env(user=cls.env.user.with_company(cls.company))
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Proveedor SIRE SAC",
                "country_id": cls.pe.id,
                "vat": "20100047218",
                "supplier_rank": 1,
            }
        )

    def _create_posted_bill(self, *, serie_num: str, total: float, day: int = 10):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 4, day),
                "date": date(2026, 4, day),
                "ref": serie_num,
                "invoice_line_ids": [
                    (0, 0, {"name": "X", "quantity": 1, "price_unit": total, "tax_ids": []})
                ],
            }
        )
        self.env.cr.execute("UPDATE account_move SET state='posted' WHERE id=%s", (move.id,))
        self.env.cr.execute(
            "UPDATE account_move_line SET parent_state='posted' WHERE move_id=%s", (move.id,)
        )
        move.invalidate_recordset()
        return move

    def _make_proposal_line(
        self, *, serie: str, number: str, total: float, vat: str | None = None, issue_day: int = 10
    ):
        return RceProposalLine(
            period="202604",
            cuo="1",
            doc_type_code="01",
            serie=serie,
            number=number,
            issue_date=date(2026, 4, issue_day),
            due_date=None,
            supplier_doc_type="6",
            supplier_doc_number=vat or self.supplier.vat,
            supplier_name=self.supplier.name,
            base_taxable=Decimal(str(total / 1.18)),
            igv=Decimal(str(total - total / 1.18)),
            base_untaxed=Decimal("0"),
            isc=Decimal("0"),
            total=Decimal(str(total)),
        )

    def test_exact_match(self):
        bill = self._create_posted_bill(serie_num="F001-100", total=118.0)
        prop = self._make_proposal_line(serie="F001", number="100", total=118.0)
        Move = self.env["account.move"]
        results = Move._l10n_pe_sire_reconcile_proposal([prop], "202604")
        self.assertEqual(results["matched"], 1)
        self.assertEqual(results["discrepancy"], 0)
        bill.invalidate_recordset()
        self.assertEqual(bill.l10n_pe_sire_match_status, "matched")

    def test_discrepancy_in_total(self):
        bill = self._create_posted_bill(serie_num="F001-101", total=200.0)
        prop = self._make_proposal_line(serie="F001", number="101", total=180.0)
        Move = self.env["account.move"]
        results = Move._l10n_pe_sire_reconcile_proposal([prop], "202604")
        self.assertEqual(results["discrepancy"], 1)
        self.assertEqual(results["matched"], 0)
        bill.invalidate_recordset()
        self.assertEqual(bill.l10n_pe_sire_match_status, "discrepancy")
        self.assertIn("200", bill.l10n_pe_sire_match_diff or "")

    def test_missing_in_odoo(self):
        prop = self._make_proposal_line(serie="F001", number="999", total=500.0)
        Move = self.env["account.move"]
        results = Move._l10n_pe_sire_reconcile_proposal([prop], "202604")
        self.assertEqual(results["missing_in_odoo"], 1)
        self.assertEqual(len(results["unmatched_proposals"]), 1)
        self.assertEqual(results["unmatched_proposals"][0]["serie_number"], "F001-999")

    def test_odoo_only_marked_not_matched(self):
        bill = self._create_posted_bill(serie_num="F001-200", total=300.0)
        # Propuesta vacía → el bill queda 'not_matched'
        Move = self.env["account.move"]
        results = Move._l10n_pe_sire_reconcile_proposal([], "202604")
        bill.invalidate_recordset()
        self.assertEqual(bill.l10n_pe_sire_match_status, "not_matched")
        self.assertGreaterEqual(len(results["odoo_only"]), 1)
