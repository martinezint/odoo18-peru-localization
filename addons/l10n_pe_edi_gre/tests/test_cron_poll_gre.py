# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..services.sunat_gre_rest import GreStatus


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestGreCheckStatus(TransactionCase):
    """Tests del action manual + cron de polling GRE."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Cron GRE Co",
                "country_id": cls.pe.id,
                "vat": "20131312955",
                "l10n_pe_gre_client_id": "test-id",
                "l10n_pe_gre_client_secret": "test-secret",
                "l10n_pe_edi_environment": "beta",
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente GRE",
                "country_id": cls.pe.id,
            }
        )

    def _make_doc(self, ticket=None, status=None):
        move = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "company_id": self.company.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "X",
                                "quantity": 1,
                                "price_unit": 100.0,
                                "tax_ids": [],
                            },
                        )
                    ],
                }
            )
        )
        doc = self.env["l10n.pe.edi.document"].create(
            {
                "move_id": move.id,
                "name": f"20131312955-09-T001-{move.id}.xml",
                "state": "sent",
            }
        )
        if ticket:
            doc.write({"gre_ticket": ticket, "gre_ind_estado": status or "01"})
        return doc

    # ─── action_l10n_pe_gre_check_status ─────────────────────────

    def test_check_status_without_ticket_raises(self):
        doc = self._make_doc()
        with self.assertRaisesRegex(UserError, "ticket GRE"):
            doc.action_l10n_pe_gre_check_status()

    def test_check_status_accepted_updates_state_and_cdr(self):
        doc = self._make_doc(ticket="T-OK", status="01")
        accepted = GreStatus(
            ind_estado="05",
            cdr_base64="QkFTRTY0X0NEUg==",  # base64 dummy
        )
        with patch(
            "odoo.addons.l10n_pe_edi_gre.services.sunat_gre_rest.SunatGreRestClient.get_status",
            return_value=accepted,
        ):
            doc.action_l10n_pe_gre_check_status()
        doc.invalidate_recordset()
        self.assertEqual(doc.gre_ind_estado, "05")
        self.assertEqual(doc.state, "accepted")
        self.assertTrue(doc.gre_cdr)
        self.assertTrue(doc.gre_last_status_check_at)

    def test_check_status_rejected_updates_error(self):
        doc = self._make_doc(ticket="T-REJ", status="01")
        rejected = GreStatus(
            ind_estado="03",
            error={"numError": "2335", "desError": "RUC suspendido"},
        )
        with patch(
            "odoo.addons.l10n_pe_edi_gre.services.sunat_gre_rest.SunatGreRestClient.get_status",
            return_value=rejected,
        ):
            doc.action_l10n_pe_gre_check_status()
        doc.invalidate_recordset()
        self.assertEqual(doc.gre_ind_estado, "03")
        self.assertEqual(doc.state, "rejected")
        self.assertIn("suspendido", doc.error_message or "")

    def test_check_status_in_process_keeps_state(self):
        doc = self._make_doc(ticket="T-WAIT", status="01")
        original_state = doc.state
        in_proc = GreStatus(ind_estado="01")
        with patch(
            "odoo.addons.l10n_pe_edi_gre.services.sunat_gre_rest.SunatGreRestClient.get_status",
            return_value=in_proc,
        ):
            doc.action_l10n_pe_gre_check_status()
        doc.invalidate_recordset()
        # State no debe cambiar (sigue 'sent')
        self.assertEqual(doc.state, original_state)
        # Pero el timestamp del check sí se actualiza
        self.assertTrue(doc.gre_last_status_check_at)


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestCronPollGreTickets(TransactionCase):
    """Cron busca docs con gre_ind_estado='01' y los pollea."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Cron GRE Co 2",
                "country_id": cls.pe.id,
                "vat": "20131312955",
                "l10n_pe_gre_client_id": "test-id",
                "l10n_pe_gre_client_secret": "test-secret",
                "l10n_pe_edi_environment": "beta",
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "P",
                "country_id": cls.pe.id,
            }
        )

    def _make_doc(self, ticket=None, status=None):
        move = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "company_id": self.company.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "X",
                                "quantity": 1,
                                "price_unit": 100.0,
                                "tax_ids": [],
                            },
                        )
                    ],
                }
            )
        )
        doc = self.env["l10n.pe.edi.document"].create(
            {
                "move_id": move.id,
                "name": f"GRE-{move.id}.xml",
                "state": "sent",
            }
        )
        if ticket:
            doc.write({"gre_ticket": ticket, "gre_ind_estado": status or "01"})
        return doc

    def test_cron_processes_only_in_process_tickets(self):
        d1 = self._make_doc(ticket="T1", status="01")
        d2 = self._make_doc(ticket="T2", status="05")  # ya aceptado, skip
        d3 = self._make_doc(ticket="T3", status="01")
        called = []

        def _track(self_doc):
            called.append(self_doc.id)

        with patch.object(
            type(d1),
            "_gre_check_status_one",
            _track,
        ):
            self.env["l10n.pe.edi.document"]._cron_poll_gre_tickets()
        self.assertIn(d1.id, called)
        self.assertIn(d3.id, called)
        self.assertNotIn(d2.id, called)

    def test_cron_continues_on_error(self):
        d1 = self._make_doc(ticket="T1", status="01")
        d2 = self._make_doc(ticket="T2", status="01")
        processed = []

        def _track_fail_first(self_doc):
            if self_doc.id == d1.id:
                raise Exception("simulated GRE poll failure")
            processed.append(self_doc.id)

        with patch.object(
            type(d1),
            "_gre_check_status_one",
            _track_fail_first,
        ):
            self.env["l10n.pe.edi.document"]._cron_poll_gre_tickets()
        self.assertIn(d2.id, processed)
        self.assertNotIn(d1.id, processed)

    def test_cron_ir_record_exists(self):
        cron = self.env.ref(
            "l10n_pe_edi_gre.ir_cron_l10n_pe_poll_gre_tickets",
            raise_if_not_found=False,
        )
        self.assertTrue(cron, "ir.cron de polling GRE debe existir")
        self.assertEqual(cron.model_id.model, "l10n.pe.edi.document")
        self.assertIn("_cron_poll_gre_tickets", cron.code)
