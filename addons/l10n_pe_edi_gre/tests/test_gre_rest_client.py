# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Tests del cliente REST GRE — todo el I/O mockeado.

Patcheamos httpx.post y httpx.get para no tocar red.
"""

from unittest.mock import MagicMock, patch

import httpx

from odoo.tests.common import TransactionCase, tagged

from ..services.sunat_gre_rest import (
    ENDPOINTS,
    GreAuthError,
    GreRestError,
    SunatGreRestClient,
    TokenCache,
)


def _mk_response(status_code=200, json_data=None, text=""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or (str(json_data) if json_data else "")
    return resp


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestSunatGreRestClient(TransactionCase):

    def _new_client(self, environment="beta"):
        return SunatGreRestClient(
            client_id="test-client-id",
            client_secret="test-client-secret",
            ruc="20131312955",
            environment=environment,
        )

    # ─── Construcción ────────────────────────────────────────────

    def test_init_beta_endpoints(self):
        c = self._new_client("beta")
        self.assertEqual(c.endpoints, ENDPOINTS["beta"])

    def test_init_production_endpoints(self):
        c = self._new_client("production")
        self.assertEqual(c.endpoints, ENDPOINTS["production"])

    def test_invalid_environment_raises(self):
        with self.assertRaisesRegex(ValueError, "environment"):
            SunatGreRestClient(
                client_id="x", client_secret="y", ruc="r", environment="staging"
            )

    def test_missing_client_id_raises(self):
        with self.assertRaises(GreAuthError):
            SunatGreRestClient(
                client_id="", client_secret="y", ruc="r", environment="beta"
            )

    def test_missing_client_secret_raises(self):
        with self.assertRaises(GreAuthError):
            SunatGreRestClient(
                client_id="x", client_secret="", ruc="r", environment="beta"
            )

    # ─── OAuth2: get_access_token ────────────────────────────────

    def test_get_token_success_caches_token(self):
        c = self._new_client()
        token_response = _mk_response(
            200, {"access_token": "tok-123", "expires_in": 3600}
        )
        with patch("httpx.post", return_value=token_response) as mock_post:
            token = c.get_access_token()
        self.assertEqual(token, "tok-123")
        self.assertTrue(c._token_cache.is_valid())
        # Llamada al endpoint correcto
        call_args = mock_post.call_args
        self.assertIn("oauth2/token", call_args.args[0])
        # POST body
        self.assertEqual(
            call_args.kwargs["data"]["grant_type"], "client_credentials"
        )
        self.assertEqual(
            call_args.kwargs["data"]["client_id"], "test-client-id"
        )

    def test_get_token_uses_cache_if_valid(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="cached-tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        # No mock; si llama httpx.post fallaría → si no falla, usó cache.
        token = c.get_access_token()
        self.assertEqual(token, "cached-tok")

    def test_get_token_refreshes_when_force(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="old-tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        token_response = _mk_response(200, {"access_token": "new-tok", "expires_in": 3600})
        with patch("httpx.post", return_value=token_response):
            token = c.get_access_token(force_refresh=True)
        self.assertEqual(token, "new-tok")

    def test_get_token_401_raises_auth_error(self):
        c = self._new_client()
        with patch("httpx.post", return_value=_mk_response(401, text="unauthorized")):
            with self.assertRaises(GreAuthError) as ctx:
                c.get_access_token()
        self.assertEqual(ctx.exception.status_code, 401)

    def test_get_token_network_error_raises(self):
        c = self._new_client()
        with patch("httpx.post", side_effect=httpx.ConnectError("dns fail")):
            with self.assertRaisesRegex(GreAuthError, "red"):
                c.get_access_token()

    def test_get_token_response_without_access_token_raises(self):
        c = self._new_client()
        with patch("httpx.post", return_value=_mk_response(200, {"expires_in": 3600})):
            with self.assertRaisesRegex(GreAuthError, "no contiene access_token"):
                c.get_access_token()

    # ─── send_gre ────────────────────────────────────────────────

    def test_send_gre_returns_ticket(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        send_resp = _mk_response(200, {"numTicket": "1234567890"})
        with patch("httpx.post", return_value=send_resp) as mock_post:
            ticket = c.send_gre("09-T001-1", "20131312955-09-T001-1.zip", b"zip-bytes")
        self.assertEqual(ticket, "1234567890")
        # Verifica URL incluye el num_doc
        call_args = mock_post.call_args
        self.assertIn("comprobantes/09-T001-1", call_args.args[0])
        # Body contiene hashZip + arcGreZip
        body = call_args.kwargs["json"]
        self.assertIn("hashZip", body["archivo"])
        self.assertIn("arcGreZip", body["archivo"])
        # Authorization header
        self.assertEqual(
            call_args.kwargs["headers"]["Authorization"], "Bearer tok"
        )

    def test_send_gre_401_refreshes_token_and_retries(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="old-tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        # 1ra llamada: 401 / 2da llamada (token refresh): 200 / 3ra (send retry): 200
        send_401 = _mk_response(401, text="token expired")
        token_response = _mk_response(200, {"access_token": "new-tok", "expires_in": 3600})
        send_ok = _mk_response(200, {"numTicket": "9999"})

        post_responses = [send_401, token_response, send_ok]
        with patch("httpx.post", side_effect=post_responses):
            ticket = c.send_gre("09-T001-1", "f.zip", b"zip")
        self.assertEqual(ticket, "9999")

    def test_send_gre_4xx_raises_with_sunat_code(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        err_resp = _mk_response(400, {"cod": "1503", "msg": "Hash inválido"})
        with patch("httpx.post", return_value=err_resp):
            with self.assertRaises(GreRestError) as ctx:
                c.send_gre("09-T001-1", "f.zip", b"zip")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.sunat_code, "1503")

    def test_send_gre_no_ticket_in_response_raises(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        # 200 OK pero sin numTicket
        with patch("httpx.post", return_value=_mk_response(200, {"otra_key": "x"})):
            with self.assertRaisesRegex(GreRestError, "sin numTicket"):
                c.send_gre("09-T001-1", "f.zip", b"zip")

    # ─── get_status ──────────────────────────────────────────────

    def test_get_status_accepted(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        status_resp = _mk_response(200, {
            "codRespuesta": "0",
            "indEstado": "05",
            "arcCdr": "ZklSb289CdrBytes==",
        })
        with patch("httpx.get", return_value=status_resp) as mock_get:
            status = c.get_status("ticket-123")
        self.assertEqual(status.ind_estado, "05")
        self.assertTrue(status.is_accepted)
        self.assertEqual(status.cdr_base64, "ZklSb289CdrBytes==")
        # URL incluye ticket
        self.assertIn("envios/ticket-123", mock_get.call_args.args[0])

    def test_get_status_in_process(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.get", return_value=_mk_response(200, {
            "codRespuesta": "0", "indEstado": "01",
        })):
            status = c.get_status("ticket-x")
        self.assertTrue(status.is_in_process)

    def test_get_status_rejected_carries_error(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.get", return_value=_mk_response(200, {
            "codRespuesta": "98",
            "indEstado": "03",
            "error": {"numError": "2335", "desError": "RUC no activo"},
        })):
            status = c.get_status("t")
        self.assertTrue(status.is_rejected)
        self.assertEqual(status.error["numError"], "2335")

    def test_get_status_5xx_raises(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.get", return_value=_mk_response(500, text="boom")):
            with self.assertRaises(GreRestError) as ctx:
                c.get_status("t")
        self.assertEqual(ctx.exception.status_code, 500)

    def test_get_status_network_error(self):
        c = self._new_client()
        from datetime import datetime, timedelta, timezone
        c._token_cache = TokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.get", side_effect=httpx.ReadTimeout("slow")):
            with self.assertRaisesRegex(GreRestError, "red"):
                c.get_status("t")
