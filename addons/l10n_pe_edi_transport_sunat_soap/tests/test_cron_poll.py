# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_edi_transport_sunat_soap")
class TestCronPollSummaryTickets(TransactionCase):
    """Cron busca docs con sunat_summary_status_code='98' y los pollea."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Cron Co",
                "country_id": cls.pe.id,
                "vat": "20131312955",
                "l10n_pe_edi_sol_user": "MODDATOS",
                "l10n_pe_edi_sol_password": "MODDATOS",
                "l10n_pe_edi_environment": "beta",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Cron",
                "country_id": cls.pe.id,
            }
        )

    def _make_doc(self, ticket=None, status="98"):
        """Crea un l10n.pe.edi.document con un move dummy."""
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
                "name": f"20131312955-RC-{move.id}.xml",
                "xml_signed": base64.b64encode(b"<fake/>"),
                "state": "sent",
            }
        )
        if ticket:
            doc.write(
                {
                    "sunat_summary_ticket": ticket,
                    "sunat_summary_status_code": status,
                }
            )
        return doc

    def test_cron_skips_docs_without_ticket(self):
        # Doc sin ticket no se procesa
        doc = self._make_doc()
        called = []

        def _track(self_doc):
            called.append(self_doc.id)

        with patch.object(
            type(doc),
            "_check_summary_status_one",
            _track,
        ):
            self.env["l10n.pe.edi.document"]._cron_poll_summary_tickets()
        self.assertNotIn(doc.id, called)

    def test_cron_skips_docs_already_done(self):
        # Doc con ticket pero status='0' (done) no se procesa
        doc = self._make_doc(ticket="T-DONE", status="0")
        called = []

        def _track(self_doc):
            called.append(self_doc.id)

        with patch.object(
            type(doc),
            "_check_summary_status_one",
            _track,
        ):
            self.env["l10n.pe.edi.document"]._cron_poll_summary_tickets()
        self.assertNotIn(doc.id, called)

    def test_cron_processes_docs_in_status_98(self):
        doc_a = self._make_doc(ticket="T-A", status="98")
        doc_b = self._make_doc(ticket="T-B", status="98")
        called = []

        def _track(self_doc):
            called.append(self_doc.id)

        with patch.object(
            type(doc_a),
            "_check_summary_status_one",
            _track,
        ):
            self.env["l10n.pe.edi.document"]._cron_poll_summary_tickets()
        self.assertIn(doc_a.id, called)
        self.assertIn(doc_b.id, called)

    def test_cron_continues_on_per_doc_error(self):
        """Si un doc falla, los demás siguen procesándose."""
        doc_a = self._make_doc(ticket="T-A", status="98")
        doc_b = self._make_doc(ticket="T-B", status="98")
        processed = []

        def _track_a_fail(self_doc):
            if self_doc.id == doc_a.id:
                raise Exception("simulated failure")
            processed.append(self_doc.id)

        with patch.object(
            type(doc_a),
            "_check_summary_status_one",
            _track_a_fail,
        ):
            # No debe re-lanzar
            self.env["l10n.pe.edi.document"]._cron_poll_summary_tickets()

        # doc_b sí se procesó a pesar del error en doc_a
        self.assertIn(doc_b.id, processed)
        self.assertNotIn(doc_a.id, processed)

    def test_cron_ir_record_exists(self):
        """El ir.cron debe estar creado tras instalar el módulo."""
        cron = self.env.ref(
            "l10n_pe_edi_transport_sunat_soap.ir_cron_l10n_pe_poll_summary_tickets",
            raise_if_not_found=False,
        )
        self.assertTrue(cron, "ir.cron de polling RC debe existir")
        self.assertEqual(cron.model_id.model, "l10n.pe.edi.document")
        self.assertIn("_cron_poll_summary_tickets", cron.code)
