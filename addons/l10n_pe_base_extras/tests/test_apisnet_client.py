# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from unittest.mock import MagicMock, patch

import requests

from odoo.tests.common import TransactionCase, tagged

from ..services.apisnet import ApisNetClient, ApisNetError


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


@tagged("post_install", "-at_install", "l10n_pe_base_extras")
class TestApisNetClient(TransactionCase):
    """Unit tests del cliente HTTP — todo el I/O está mockeado."""

    def setUp(self):
        super().setUp()
        self.client = ApisNetClient(token="test-token-123")

    # ─── Construcción ────────────────────────────────────────────────

    def test_init_without_token_raises(self):
        with self.assertRaises(ApisNetError):
            ApisNetClient(token="")

    def test_init_with_token_ok(self):
        c = ApisNetClient(token="abc")
        self.assertEqual(c.token, "abc")
        self.assertEqual(c.base_url, "https://api.apis.net.pe/v1")

    # ─── consult_ruc ─────────────────────────────────────────────────

    def test_consult_ruc_200(self):
        sample = {
            "ruc": "20131312955",
            "razonSocial": "SUNAT",
            "estado": "ACTIVO",
            "condicion": "HABIDO",
            "direccion": "AV. GARCILASO DE LA VEGA 1472",
            "departamento": "LIMA",
            "provincia": "LIMA",
            "distrito": "LIMA",
            "ubigeo": "150101",
        }
        with patch("requests.get", return_value=_mock_response(200, sample)) as mock_get:
            result = self.client.consult_ruc("20131312955")
        self.assertEqual(result, sample)
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        self.assertEqual(call_kwargs["params"], {"numero": "20131312955"})
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer test-token-123")

    def test_consult_ruc_404_returns_none(self):
        with patch("requests.get", return_value=_mock_response(404)):
            result = self.client.consult_ruc("99999999999")
        self.assertIsNone(result)

    def test_consult_ruc_401_raises(self):
        with patch("requests.get", return_value=_mock_response(401)):
            with self.assertRaisesRegex(ApisNetError, "Token.*inválido"):
                self.client.consult_ruc("20131312955")

    def test_consult_ruc_429_raises(self):
        with patch("requests.get", return_value=_mock_response(429)):
            with self.assertRaisesRegex(ApisNetError, "Cuota.*excedida"):
                self.client.consult_ruc("20131312955")

    def test_consult_ruc_422_raises(self):
        with patch("requests.get", return_value=_mock_response(422)):
            with self.assertRaisesRegex(ApisNetError, "Formato.*inválido"):
                self.client.consult_ruc("bad")

    def test_consult_ruc_timeout_raises(self):
        with patch("requests.get", side_effect=requests.exceptions.Timeout()):
            with self.assertRaisesRegex(ApisNetError, "Timeout"):
                self.client.consult_ruc("20131312955")

    def test_consult_ruc_connection_error_raises(self):
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("boom")):
            with self.assertRaisesRegex(ApisNetError, "Error de conexión"):
                self.client.consult_ruc("20131312955")

    # ─── consult_dni ─────────────────────────────────────────────────

    def test_consult_dni_200(self):
        sample = {
            "dni": "12345678",
            "nombres": "JUAN",
            "apellidoPaterno": "PEREZ",
            "apellidoMaterno": "GARCIA",
        }
        with patch("requests.get", return_value=_mock_response(200, sample)):
            result = self.client.consult_dni("12345678")
        self.assertEqual(result, sample)

    def test_consult_dni_404_returns_none(self):
        with patch("requests.get", return_value=_mock_response(404)):
            result = self.client.consult_dni("00000000")
        self.assertIsNone(result)
