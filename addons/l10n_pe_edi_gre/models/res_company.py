# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    # ─── Credenciales SUNAT GRE 2.0 (OAuth2 client_credentials) ────────

    l10n_pe_gre_client_id = fields.Char(
        string="Client ID GRE (SUNAT)",
        groups="base.group_system",
        help="Client ID OAuth2 emitido por SUNAT para la API GRE 2.0. "
             "Se obtiene en Mis Aplicaciones del portal SUNAT.",
    )
    l10n_pe_gre_client_secret = fields.Char(
        string="Client Secret GRE",
        groups="base.group_system",
    )

    # ─── Token cache (persistente) ─────────────────────────────────────
    # Evita pedir token a SUNAT en cada llamada. Refresh automático cuando
    # caduca (vigencia típica 1h).

    l10n_pe_gre_token = fields.Char(
        string="GRE access_token (cache)",
        groups="base.group_system",
        copy=False,
    )
    l10n_pe_gre_token_expires_at = fields.Datetime(
        string="GRE token expira",
        groups="base.group_system",
        copy=False,
    )

    def _get_l10n_pe_gre_rest_client(self):
        """Devuelve un SunatGreRestClient ya autenticado.

        Reusa el token cacheado en la company si aún es válido (>30s de margen).
        """
        self.ensure_one()
        if not self.vat:
            raise UserError(_("Empresa %s no tiene RUC configurado.") % self.name)
        if not self.l10n_pe_gre_client_id or not self.l10n_pe_gre_client_secret:
            raise UserError(_(
                "Faltan credenciales GRE (Client ID / Secret) en la empresa %s."
            ) % self.name)

        from ..services.sunat_gre_rest import SunatGreRestClient, TokenCache

        cache = TokenCache()
        if self.l10n_pe_gre_token and self.l10n_pe_gre_token_expires_at:
            cache.token = self.l10n_pe_gre_token
            # El field es naive; SUNAT/UTC. Asumimos almacenado en UTC.
            expires = self.l10n_pe_gre_token_expires_at
            from datetime import timezone
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            cache.expires_at = expires

        return SunatGreRestClient(
            client_id=self.l10n_pe_gre_client_id,
            client_secret=self.l10n_pe_gre_client_secret,
            ruc=self.vat.strip(),
            environment=self.l10n_pe_edi_environment or "beta",
            token_cache=cache,
        )

    def _persist_l10n_pe_gre_token(self, token: str, expires_at):
        """Guarda en BD el token recién obtenido (llamado tras refresh)."""
        self.ensure_one()
        self.sudo().write({
            "l10n_pe_gre_token": token,
            "l10n_pe_gre_token_expires_at": expires_at,
        })
