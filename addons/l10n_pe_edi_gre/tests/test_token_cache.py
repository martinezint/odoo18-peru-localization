# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import datetime, timedelta, timezone

from odoo.tests.common import TransactionCase, tagged

from ..services.sunat_gre_rest import (
    ESTADO_ACEPTADO,
    ESTADO_EN_PROCESO,
    ESTADO_RECHAZADO,
    ESTADO_ANULADO,
    GreStatus,
    TokenCache,
)


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestTokenCache(TransactionCase):
    """TokenCache es lógica pura — sin red."""

    def test_empty_cache_not_valid(self):
        cache = TokenCache()
        self.assertFalse(cache.is_valid())

    def test_expired_cache_not_valid(self):
        cache = TokenCache(
            token="abc",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        self.assertFalse(cache.is_valid())

    def test_fresh_token_is_valid(self):
        cache = TokenCache(
            token="abc",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        self.assertTrue(cache.is_valid())

    def test_within_safety_window_treated_as_expired(self):
        """Si el token expira en <30s, lo consideramos expirado por seguridad."""
        cache = TokenCache(
            token="abc",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=15),
        )
        self.assertFalse(cache.is_valid(safety_window_sec=30))

    def test_custom_safety_window(self):
        cache = TokenCache(
            token="abc",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=15),
        )
        # Con safety_window de 5s, el token de 15s aún sirve
        self.assertTrue(cache.is_valid(safety_window_sec=5))


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestGreStatus(TransactionCase):
    """Estados SUNAT GRE: indEstado 01/03/05/11."""

    def test_in_process(self):
        s = GreStatus(ind_estado=ESTADO_EN_PROCESO)
        self.assertTrue(s.is_in_process)
        self.assertFalse(s.is_accepted)
        self.assertFalse(s.is_rejected)
        self.assertFalse(s.is_cancelled)

    def test_accepted(self):
        s = GreStatus(ind_estado=ESTADO_ACEPTADO, cdr_base64="abc")
        self.assertTrue(s.is_accepted)
        self.assertFalse(s.is_in_process)

    def test_rejected(self):
        s = GreStatus(ind_estado=ESTADO_RECHAZADO)
        self.assertTrue(s.is_rejected)
        self.assertFalse(s.is_accepted)

    def test_cancelled(self):
        s = GreStatus(ind_estado=ESTADO_ANULADO)
        self.assertTrue(s.is_cancelled)

    def test_unknown_estado_all_false(self):
        s = GreStatus(ind_estado="99")
        self.assertFalse(s.is_in_process)
        self.assertFalse(s.is_accepted)
        self.assertFalse(s.is_rejected)
        self.assertFalse(s.is_cancelled)
