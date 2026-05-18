# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..services.sunat_sire_rest import SireTicketStatus


@tagged("post_install", "-at_install", "l10n_pe_sire")
class TestSirePeriodModel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create({
            "name": "Test SIRE Co",
            "country_id": cls.pe.id,
            "vat": "20131312955",
            "l10n_pe_sire_client_id": "test-client",
            "l10n_pe_sire_client_secret": "test-secret",
            "l10n_pe_edi_environment": "beta",
        })

    def _make_period(self, periodo="202604", libro="rce"):
        return self.env["l10n.pe.sire.period"].create({
            "company_id": self.company.id,
            "periodo": periodo,
            "libro": libro,
        })

    # ─── Validaciones ────────────────────────────────────────────

    def test_invalid_periodo_format_raises(self):
        with self.assertRaisesRegex(ValidationError, "YYYYMM"):
            self._make_period("2026M4")

    def test_invalid_periodo_length_raises(self):
        with self.assertRaisesRegex(ValidationError, "YYYYMM"):
            self._make_period("20260")

    def test_invalid_month_raises(self):
        with self.assertRaisesRegex(ValidationError, "[Mm]es"):
            self._make_period("202613")

    def test_invalid_year_raises(self):
        with self.assertRaisesRegex(ValidationError, "[Aa]ño"):
            self._make_period("201712")

    def test_unique_company_periodo_libro(self):
        self._make_period("202604", "rce")
        with self.assertRaisesRegex(Exception, "unique|UNIQUE"):
            self._make_period("202604", "rce")

    def test_same_period_different_libro_ok(self):
        rce = self._make_period("202604", "rce")
        rvie = self._make_period("202604", "rvie")
        self.assertNotEqual(rce.id, rvie.id)

    def test_display_name_includes_periodo_and_libro(self):
        rec = self._make_period("202604", "rvie")
        self.assertIn("202604", rec.display_name)
        self.assertIn("RVIE", rec.display_name)

    # ─── State machine ───────────────────────────────────────────

    def test_request_propuesta_updates_state_and_ticket(self):
        period = self._make_period("202605", "rce")
        with patch(
            "odoo.addons.l10n_pe_sire.services.sunat_sire_rest."
            "SunatSireRestClient.request_rce_propuesta",
            return_value="T-ABC-123",
        ):
            period.action_request_propuesta()
        period.invalidate_recordset()
        self.assertEqual(period.state, "requested")
        self.assertEqual(period.ticket, "T-ABC-123")
        self.assertTrue(period.ticket_requested_at)

    def test_check_ticket_done_moves_to_ready(self):
        period = self._make_period("202605", "rce")
        period.write({
            "state": "requested",
            "ticket": "T-1",
        })
        done_status = SireTicketStatus(
            cod_estado="02",
            descripcion_estado="TERMINADO",
            archivo_url="https://x/y.txt",
            archivo_nombre="RCE.txt",
        )
        with patch(
            "odoo.addons.l10n_pe_sire.services.sunat_sire_rest."
            "SunatSireRestClient.get_ticket_status",
            return_value=done_status,
        ):
            period.action_check_ticket()
        period.invalidate_recordset()
        self.assertEqual(period.state, "ready")
        self.assertEqual(period.file_url, "https://x/y.txt")
        self.assertEqual(period.file_name, "RCE.txt")

    def test_check_ticket_in_process_stays_in_requested(self):
        period = self._make_period("202605", "rce")
        period.write({"state": "requested", "ticket": "T-1"})
        in_proc = SireTicketStatus(cod_estado="01", descripcion_estado="EN PROCESO")
        with patch(
            "odoo.addons.l10n_pe_sire.services.sunat_sire_rest."
            "SunatSireRestClient.get_ticket_status",
            return_value=in_proc,
        ):
            period.action_check_ticket()
        period.invalidate_recordset()
        self.assertEqual(period.state, "requested")
        self.assertEqual(period.ticket_cod_estado, "01")

    def test_check_ticket_error_moves_to_error(self):
        period = self._make_period("202605", "rce")
        period.write({"state": "requested", "ticket": "T-1"})
        err = SireTicketStatus(cod_estado="03", descripcion_estado="No se encontró info")
        with patch(
            "odoo.addons.l10n_pe_sire.services.sunat_sire_rest."
            "SunatSireRestClient.get_ticket_status",
            return_value=err,
        ):
            period.action_check_ticket()
        period.invalidate_recordset()
        self.assertEqual(period.state, "error")
        self.assertIn("No se encontró", period.error_message)

    def test_download_writes_file_and_advances_state(self):
        period = self._make_period("202605", "rce")
        period.write({
            "state": "ready",
            "ticket": "T-1",
            "file_url": "https://x/file.txt",
            "file_name": "file.txt",
        })
        with patch(
            "odoo.addons.l10n_pe_sire.services.sunat_sire_rest."
            "SunatSireRestClient.download_file",
            return_value=b"TXT_CONTENT",
        ):
            period.action_download()
        period.invalidate_recordset()
        self.assertEqual(period.state, "downloaded")
        self.assertTrue(period.file_data)
        self.assertTrue(period.downloaded_at)
