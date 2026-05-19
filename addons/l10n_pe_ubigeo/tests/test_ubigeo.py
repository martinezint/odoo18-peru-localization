# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_ubigeo")
class TestUbigeo(TransactionCase):
    def test_seed_data_loaded(self):
        """Verifica que el dataset semilla está disponible tras instalar."""
        lima_cercado = self.env.ref("l10n_pe_ubigeo.ubigeo_150101", raise_if_not_found=False)
        self.assertTrue(lima_cercado)
        self.assertEqual(lima_cercado.department, "Lima")
        self.assertEqual(lima_cercado.district, "Lima (Cercado)")

    def test_display_name_format(self):
        u = self.env.ref("l10n_pe_ubigeo.ubigeo_150122")
        self.assertIn("150122", u.display_name)
        self.assertIn("Miraflores", u.display_name)
        self.assertIn("Lima", u.display_name)

    def test_unique_code_constraint(self):
        from psycopg2.errors import UniqueViolation

        with self.assertRaises(UniqueViolation):
            with self.env.cr.savepoint():
                self.env["l10n.pe.ubigeo"].create(
                    {
                        "code": "150101",  # ya existe en data
                        "department": "X",
                        "province": "Y",
                        "district": "Z",
                    }
                )
                self.env.flush_all()

    def test_invalid_code_format_short(self):
        with self.assertRaises(ValidationError):
            self.env["l10n.pe.ubigeo"].create(
                {
                    "code": "12345",  # 5 dígitos
                    "department": "X",
                    "province": "Y",
                    "district": "Z",
                }
            )

    def test_invalid_code_format_alpha(self):
        with self.assertRaises(ValidationError):
            self.env["l10n.pe.ubigeo"].create(
                {
                    "code": "ABC123",  # tiene letras
                    "department": "X",
                    "province": "Y",
                    "district": "Z",
                }
            )

    def test_name_search_by_district(self):
        Ubigeo = self.env["l10n.pe.ubigeo"]
        results = Ubigeo.name_search("Miraflores", limit=5)
        self.assertTrue(results)
        names = [r[1] for r in results]
        self.assertTrue(any("Miraflores" in n for n in names))

    def test_name_search_by_code(self):
        Ubigeo = self.env["l10n.pe.ubigeo"]
        results = Ubigeo.name_search("150122", limit=5)
        self.assertEqual(len(results), 1)
        self.assertIn("Miraflores", results[0][1])

    def test_24_departamentos_capitales(self):
        """El dataset incluye la capital de los 24 departamentos peruanos."""
        # Códigos de departamentos peruanos: 01-25 (sin 15 ya cubierto por Lima)
        codes = [
            "010101",  # Amazonas
            "020101",  # Áncash
            "030101",  # Apurímac
            "040101",  # Arequipa
            "050101",  # Ayacucho
            "060101",  # Cajamarca
            "070101",  # Callao
            "080101",  # Cusco
            "090101",  # Huancavelica
            "100101",  # Huánuco
            "110101",  # Ica
            "120101",  # Junín
            "130101",  # La Libertad
            "140101",  # Lambayeque
            "160101",  # Loreto
            "170101",  # Madre de Dios
            "180101",  # Moquegua
            "190101",  # Pasco
            "200101",  # Piura
            "210101",  # Puno
            "220101",  # San Martín
            "230101",  # Tacna
            "240101",  # Tumbes
            "250101",  # Ucayali
        ]
        found = self.env["l10n.pe.ubigeo"].search([("code", "in", codes)])
        self.assertEqual(len(found), len(codes))
