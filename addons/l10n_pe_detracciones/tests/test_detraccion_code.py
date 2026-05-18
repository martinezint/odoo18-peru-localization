# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_detracciones")
class TestDetraccionCode(TransactionCase):
    def test_some_canonical_codes_loaded(self):
        """Verifica que los códigos más usados están cargados como data."""
        for xmlid, code, pct in [
            ("l10n_pe_detracciones.det_002", "002", 4.0),  # Arroz pilado
            ("l10n_pe_detracciones.det_022", "022", 12.0),  # Otros servicios empresariales
            ("l10n_pe_detracciones.det_037", "037", 12.0),  # Demás servicios gravados IGV
        ]:
            rec = self.env.ref(xmlid)
            self.assertEqual(rec.code, code)
            self.assertEqual(rec.percentage, pct)

    def test_count_canonical_codes(self):
        """Debemos haber cargado al menos 20 códigos SUNAT comunes."""
        n = self.env["l10n.pe.detraccion.code"].search_count([])
        self.assertGreaterEqual(n, 20, f"Esperamos >= 20 códigos, hay {n}")

    def test_code_unique_constraint(self):
        existing = self.env.ref("l10n_pe_detracciones.det_001")
        with self.assertRaisesRegex(Exception, "unique"):
            self.env["l10n.pe.detraccion.code"].create(
                {
                    "code": existing.code,
                    "name": "Duplicado",
                    "anexo": "2",
                    "percentage": 5.0,
                }
            )

    def test_percentage_must_be_positive(self):
        with self.assertRaisesRegex(ValidationError, "porcentaje"):
            self.env["l10n.pe.detraccion.code"].create(
                {
                    "code": "999",
                    "name": "Test",
                    "anexo": "2",
                    "percentage": 0,
                }
            )

    def test_percentage_max_100(self):
        with self.assertRaisesRegex(ValidationError, "porcentaje"):
            self.env["l10n.pe.detraccion.code"].create(
                {
                    "code": "998",
                    "name": "Test",
                    "anexo": "2",
                    "percentage": 150.0,
                }
            )

    def test_display_name(self):
        rec = self.env.ref("l10n_pe_detracciones.det_002")
        self.assertEqual(rec.display_name, "[002] Arroz pilado (4.0%)")
