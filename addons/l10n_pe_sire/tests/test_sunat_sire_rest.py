# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx

from odoo.tests.common import TransactionCase, tagged

from ..services.sunat_sire_rest import (
    ESTADO_EN_PROCESO,
    ESTADO_TERMINADO,
    SIRE_BASE,
    SireAuthError,
    SireError,
    SireTicketStatus,
    SireTokenCache,
    SunatSireRestClient,
)


def _mk_response(status_code=200, json_data=None, text="", content=b""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or (str(json_data) if json_data else "")
    resp.content = content or (resp.text.encode("utf-8") if resp.text else b"")
    return resp


@tagged("post_install", "-at_install", "l10n_pe_sire")
class TestSireTokenCache(TransactionCase):

    def test_empty_not_valid(self):
        self.assertFalse(SireTokenCache().is_valid())

    def test_fresh_valid(self):
        c = SireTokenCache(
            token="x",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        self.assertTrue(c.is_valid())

    def test_expired_invalid(self):
        c = SireTokenCache(
            token="x",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        )
        self.assertFalse(c.is_valid())


@tagged("post_install", "-at_install", "l10n_pe_sire")
class TestSireTicketStatus(TransactionCase):

    def test_in_process(self):
        s = SireTicketStatus(cod_estado=ESTADO_EN_PROCESO)
        self.assertTrue(s.is_in_process)
        self.assertFalse(s.is_done)
        self.assertFalse(s.is_error)

    def test_done(self):
        s = SireTicketStatus(cod_estado=ESTADO_TERMINADO, archivo_url="http://x")
        self.assertTrue(s.is_done)
        self.assertFalse(s.is_in_process)

    def test_error(self):
        s = SireTicketStatus(cod_estado="03", descripcion_estado="fallo X")
        self.assertTrue(s.is_error)


@tagged("post_install", "-at_install", "l10n_pe_sire")
class TestSunatSireRestClient(TransactionCase):

    def _new_client(self, environment="beta"):
        return SunatSireRestClient(
            client_id="sire-client",
            client_secret="sire-secret",
            ruc="20131312955",
            environment=environment,
        )

    # ─── Construcción ────────────────────────────────────────────

    def test_beta_uses_beta_base(self):
        c = self._new_client("beta")
        self.assertEqual(c.base, SIRE_BASE["beta"])

    def test_production_uses_prod_base(self):
        c = self._new_client("production")
        self.assertEqual(c.base, SIRE_BASE["production"])

    def test_invalid_env_raises(self):
        with self.assertRaisesRegex(ValueError, "environment"):
            SunatSireRestClient(
                client_id="x", client_secret="y", ruc="r", environment="staging"
            )

    def test_missing_creds_raise_auth_error(self):
        with self.assertRaises(SireAuthError):
            SunatSireRestClient(
                client_id="", client_secret="y", ruc="r", environment="beta"
            )

    # ─── Validación de período ───────────────────────────────────

    def test_periodo_invalid_length(self):
        c = self._new_client()
        with self.assertRaisesRegex(ValueError, "YYYYMM"):
            c.request_rce_propuesta("20260")  # 5 dígitos

    def test_periodo_non_digit(self):
        c = self._new_client()
        with self.assertRaisesRegex(ValueError, "YYYYMM"):
            c.request_rce_propuesta("2026MA")

    def test_periodo_invalid_month(self):
        c = self._new_client()
        with self.assertRaisesRegex(ValueError, "mes"):
            c.request_rce_propuesta("202613")

    def test_periodo_invalid_year(self):
        c = self._new_client()
        with self.assertRaisesRegex(ValueError, "año"):
            c.request_rce_propuesta("201712")  # < 2018

    # ─── OAuth2 ──────────────────────────────────────────────────

    def test_get_token_success(self):
        c = self._new_client()
        token_resp = _mk_response(200, {"access_token": "tok-sire", "expires_in": 3600})
        with patch("httpx.post", return_value=token_resp) as mock_post:
            token = c.get_access_token()
        self.assertEqual(token, "tok-sire")
        # Verify scope va a SIRE, no GRE
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(
            call_kwargs["data"]["scope"], "https://api-sire.sunat.gob.pe"
        )

    def test_get_token_401_raises(self):
        c = self._new_client()
        with patch("httpx.post", return_value=_mk_response(401, text="bad creds")):
            with self.assertRaises(SireAuthError):
                c.get_access_token()

    def test_get_token_no_access_token_raises(self):
        c = self._new_client()
        with patch("httpx.post", return_value=_mk_response(200, {"expires_in": 3600})):
            with self.assertRaisesRegex(SireAuthError, "sin access_token"):
                c.get_access_token()

    # ─── request_rce_propuesta ───────────────────────────────────

    def test_request_rce_returns_ticket(self):
        c = self._new_client()
        c._token_cache = SireTokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        send_resp = _mk_response(200, {"numTicket": "T-12345"})
        with patch("httpx.request", return_value=send_resp) as mock_req:
            ticket = c.request_rce_propuesta("202604")
        self.assertEqual(ticket, "T-12345")
        call = mock_req.call_args
        self.assertEqual(call.args[0], "POST")
        # URL contiene período + path RCE
        self.assertIn("rce/propuesta", call.args[1])
        self.assertIn("202604", call.args[1])
        # Authorization header
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer tok")

    def test_request_rce_no_ticket_raises(self):
        c = self._new_client()
        c._token_cache = SireTokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.request", return_value=_mk_response(200, {"otra": "x"})):
            with self.assertRaisesRegex(SireError, "sin numTicket"):
                c.request_rce_propuesta("202604")

    def test_request_rce_error_status(self):
        c = self._new_client()
        c._token_cache = SireTokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.request", return_value=_mk_response(
            400, {"cod": "9001", "msg": "Período no abierto"}
        )):
            with self.assertRaises(SireError) as ctx:
                c.request_rce_propuesta("202604")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.sunat_code, "9001")

    # ─── request_rvie_propuesta ──────────────────────────────────

    def test_request_rvie_returns_ticket(self):
        c = self._new_client()
        c._token_cache = SireTokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.request", return_value=_mk_response(200, {"numTicket": "V-99"})) as mock_req:
            ticket = c.request_rvie_propuesta("202604")
        self.assertEqual(ticket, "V-99")
        # URL contiene path RVIE
        self.assertIn("rvie/propuesta", mock_req.call_args.args[1])

    # ─── get_ticket_status ───────────────────────────────────────

    def test_get_ticket_status_done_with_file(self):
        c = self._new_client()
        c._token_cache = SireTokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        status_resp = _mk_response(200, {
            "codEstado": "02",
            "desEstado": "TERMINADO",
            "archivo": {"url": "https://download/x.txt", "nombre": "RCE-202604.txt"},
        })
        with patch("httpx.request", return_value=status_resp):
            status = c.get_ticket_status("T-12345", libro="rce")
        self.assertTrue(status.is_done)
        self.assertEqual(status.archivo_url, "https://download/x.txt")
        self.assertEqual(status.archivo_nombre, "RCE-202604.txt")

    def test_get_ticket_status_in_process(self):
        c = self._new_client()
        c._token_cache = SireTokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.request", return_value=_mk_response(200, {
            "codEstado": "01", "desEstado": "EN PROCESO",
        })):
            status = c.get_ticket_status("T-12345", libro="rce")
        self.assertTrue(status.is_in_process)

    def test_get_ticket_status_invalid_libro_raises(self):
        c = self._new_client()
        with self.assertRaisesRegex(ValueError, "libro"):
            c.get_ticket_status("T-1", libro="foo")

    # ─── download_file ───────────────────────────────────────────

    def test_download_file_returns_content(self):
        c = self._new_client()
        c._token_cache = SireTokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.request", return_value=_mk_response(200, content=b"TXT_DATA")):
            data = c.download_file("https://x.com/file.txt")
        self.assertEqual(data, b"TXT_DATA")

    def test_download_file_error_raises(self):
        c = self._new_client()
        c._token_cache = SireTokenCache(
            token="tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        with patch("httpx.request", return_value=_mk_response(404, text="not found")):
            with self.assertRaises(SireError):
                c.download_file("https://x.com/missing.txt")

    # ─── 401 retry ───────────────────────────────────────────────

    def test_401_refreshes_token_and_retries(self):
        c = self._new_client()
        c._token_cache = SireTokenCache(
            token="old-tok",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        # 1ra request: 401 / refresh: 200 / 2da request: 200
        first_401 = _mk_response(401, text="expired")
        ok_resp = _mk_response(200, {"numTicket": "T1"})
        token_refresh = _mk_response(200, {"access_token": "new-tok", "expires_in": 3600})

        with patch("httpx.request", side_effect=[first_401, ok_resp]), \
             patch("httpx.post", return_value=token_refresh):
            ticket = c.request_rce_propuesta("202604")
        self.assertEqual(ticket, "T1")
