# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

# RUCs reales conocidos (públicos, fácilmente verificables):
RUC_VALID_SUNAT = "20131312955"  # SUNAT
RUC_VALID_BCP = "20100047218"  # Banco de Crédito del Perú
RUC_INVALID_CHECKSUM = "20131312954"  # Último dígito mal
RUC_SHORT = "201313129"  # 9 dígitos
RUC_NON_NUMERIC = "2013131295A"  # Letra al final

DNI_VALID = "12345678"
DNI_SHORT = "1234567"
DNI_LETTERS = "1234567A"

CE_VALID = "001234567"  # 9 chars alfanuméricos
CE_TOO_SHORT = "12345"  # 5 chars
CE_TOO_LONG = "1234567890123"  # 13 chars


@tagged("post_install", "-at_install", "l10n_pe_base_extras")
class TestRucValidation(TransactionCase):
    """Valida que el constraint rechaza/acepta correctamente según tipo SUNAT."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.it_ruc = cls.env.ref("l10n_pe.it_RUC")
        cls.it_dni = cls.env.ref("l10n_pe.it_DNI")
        # Cédula extranjera vive en l10n_latam_base como "it_fid" (foreign ID).
        # En el catálogo SUNAT 06 corresponde al código "4".
        cls.it_ce = cls.env.ref("l10n_latam_base.it_fid")
        cls.pe = cls.env.ref("base.pe")

    def _make(self, name, vat, id_type):
        return self.env["res.partner"].create(
            {
                "name": name,
                "vat": vat,
                "country_id": self.pe.id,
                "l10n_latam_identification_type_id": id_type.id,
            }
        )

    # ─── RUC ─────────────────────────────────────────────────────────

    def test_ruc_valid_sunat(self):
        partner = self._make("SUNAT", RUC_VALID_SUNAT, self.it_ruc)
        self.assertTrue(partner.id)

    def test_ruc_valid_bcp(self):
        partner = self._make("BCP", RUC_VALID_BCP, self.it_ruc)
        self.assertTrue(partner.id)

    def test_ruc_invalid_checksum(self):
        with self.assertRaisesRegex(ValidationError, "RUC.*inválido"):
            self._make("Bad RUC", RUC_INVALID_CHECKSUM, self.it_ruc)

    def test_ruc_too_short(self):
        with self.assertRaisesRegex(ValidationError, "RUC.*inválido"):
            self._make("Short RUC", RUC_SHORT, self.it_ruc)

    def test_ruc_non_numeric(self):
        with self.assertRaisesRegex(ValidationError, "RUC.*inválido"):
            self._make("Letters RUC", RUC_NON_NUMERIC, self.it_ruc)

    # NOTA: base_vat (core) tiene su propio constraint sobre vat que se
    # dispara antes que el nuestro y rechaza entradas con espacios. Aceptamos
    # ese comportamiento — la limpieza de espacios es responsabilidad del UI.

    # ─── DNI ─────────────────────────────────────────────────────────

    def test_dni_valid(self):
        partner = self._make("Juan", DNI_VALID, self.it_dni)
        self.assertTrue(partner.id)

    def test_dni_too_short(self):
        with self.assertRaisesRegex(ValidationError, "DNI.*inválido"):
            self._make("Short DNI", DNI_SHORT, self.it_dni)

    def test_dni_with_letters(self):
        with self.assertRaisesRegex(ValidationError, "DNI.*inválido"):
            self._make("Letters DNI", DNI_LETTERS, self.it_dni)

    # ─── CE ──────────────────────────────────────────────────────────

    def test_ce_valid(self):
        partner = self._make("Extranjero", CE_VALID, self.it_ce)
        self.assertTrue(partner.id)

    def test_ce_too_short(self):
        with self.assertRaisesRegex(ValidationError, "CE.*inválido"):
            self._make("Short CE", CE_TOO_SHORT, self.it_ce)

    def test_ce_too_long(self):
        with self.assertRaisesRegex(ValidationError, "CE.*inválido"):
            self._make("Long CE", CE_TOO_LONG, self.it_ce)

    # ─── Edge cases ──────────────────────────────────────────────────

    def test_no_vat_no_validation(self):
        """Partner sin VAT no debe disparar el constraint."""
        partner = self.env["res.partner"].create(
            {
                "name": "Sin RUC",
                "l10n_latam_identification_type_id": self.it_ruc.id,
            }
        )
        self.assertTrue(partner.id)

    def test_no_id_type_no_validation(self):
        """Sin tipo de identificación, no validamos formato."""
        partner = self.env["res.partner"].create(
            {
                "name": "Sin tipo",
                "vat": "anything",
            }
        )
        self.assertTrue(partner.id)

    def test_update_invalid_ruc_raises(self):
        """Cambiar a RUC inválido en partner existente también dispara."""
        partner = self._make("OK", RUC_VALID_SUNAT, self.it_ruc)
        with self.assertRaisesRegex(ValidationError, "RUC.*inválido"):
            partner.vat = RUC_INVALID_CHECKSUM
