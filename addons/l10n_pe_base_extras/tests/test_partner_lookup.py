# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from unittest.mock import MagicMock, patch

import requests
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


@tagged("post_install", "-at_install", "l10n_pe_base_extras")
class TestPartnerApisNetLookup(TransactionCase):
    """Tests del flujo completo: botón en partner → apis.net.pe → escritura."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.it_ruc = cls.env.ref("l10n_pe.it_RUC")
        cls.it_dni = cls.env.ref("l10n_pe.it_DNI")
        cls.pe = cls.env.ref("base.pe")
        # Garantiza token presente para los tests del flujo de consulta.
        cls.env.company.l10n_pe_apisnet_token = "test-token"

    def test_query_without_vat_raises(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Sin VAT",
                "l10n_latam_identification_type_id": self.it_ruc.id,
            }
        )
        with self.assertRaisesRegex(UserError, "número de documento"):
            partner.action_l10n_pe_query_apisnet()

    def test_query_without_id_type_raises(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Sin tipo",
                "vat": "20131312955",
            }
        )
        with self.assertRaisesRegex(UserError, "Tipo de documento"):
            partner.action_l10n_pe_query_apisnet()

    def test_query_ruc_fills_partner(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Placeholder",
                "vat": "20131312955",
                "country_id": self.pe.id,
                "l10n_latam_identification_type_id": self.it_ruc.id,
            }
        )
        sunat_data = {
            "ruc": "20131312955",
            "razonSocial": "SUPERINTENDENCIA NACIONAL DE ADUANAS Y DE ADMINISTRACION TRIBUTARIA",
            "direccion": "AV. GARCILASO DE LA VEGA 1472 LIMA",
            "estado": "ACTIVO",
        }
        with patch("requests.get", return_value=_mock_response(200, sunat_data)):
            partner.action_l10n_pe_query_apisnet()
        self.assertEqual(
            partner.name, "SUPERINTENDENCIA NACIONAL DE ADUANAS Y DE ADMINISTRACION TRIBUTARIA"
        )
        self.assertEqual(partner.street, "AV. GARCILASO DE LA VEGA 1472 LIMA")
        self.assertTrue(partner.is_company)
        self.assertEqual(partner.country_id, self.pe)

    def test_query_ruc_not_found_raises(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Phantom",
                "vat": "20100047218",
                "country_id": self.pe.id,
                "l10n_latam_identification_type_id": self.it_ruc.id,
            }
        )
        with patch("requests.get", return_value=_mock_response(404)):
            with self.assertRaisesRegex(UserError, "no encontrado en SUNAT"):
                partner.action_l10n_pe_query_apisnet()

    def test_query_dni_fills_name(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Placeholder",
                "vat": "12345678",
                "country_id": self.pe.id,
                "l10n_latam_identification_type_id": self.it_dni.id,
            }
        )
        reniec_data = {
            "dni": "12345678",
            "nombres": "JUAN CARLOS",
            "apellidoPaterno": "PEREZ",
            "apellidoMaterno": "GARCIA",
        }
        with patch("requests.get", return_value=_mock_response(200, reniec_data)):
            partner.action_l10n_pe_query_apisnet()
        self.assertEqual(partner.name, "PEREZ GARCIA JUAN CARLOS")
        self.assertFalse(partner.is_company)
