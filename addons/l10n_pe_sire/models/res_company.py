# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import UTC

from odoo import _, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    # SIRE usa client_credentials DISTINTOS de GRE (typically — SUNAT puede
    # asignar el mismo si el contribuyente lo configura así, pero por defecto
    # son aplicaciones separadas en Mis Aplicaciones del portal SUNAT).

    l10n_pe_sire_client_id = fields.Char(
        string="Client ID SIRE",
        groups="base.group_system",
        help="Client ID OAuth2 emitido por SUNAT para la API SIRE. "
        "Suele ser distinto del usado para GRE.",
    )
    l10n_pe_sire_client_secret = fields.Char(
        string="Client Secret SIRE",
        groups="base.group_system",
    )
    l10n_pe_sire_token = fields.Char(
        string="SIRE access_token (cache)",
        groups="base.group_system",
        copy=False,
    )
    l10n_pe_sire_token_expires_at = fields.Datetime(
        string="SIRE token expira",
        groups="base.group_system",
        copy=False,
    )

    def _get_l10n_pe_sire_rest_client(self):
        self.ensure_one()
        if not self.vat:
            raise UserError(_("Empresa %s no tiene RUC configurado.") % self.name)
        if not self.l10n_pe_sire_client_id or not self.l10n_pe_sire_client_secret:
            raise UserError(
                _("Faltan credenciales SIRE (Client ID / Secret) en la empresa %s.") % self.name
            )

        from ..services.sunat_sire_rest import SireTokenCache, SunatSireRestClient

        cache = SireTokenCache()
        if self.l10n_pe_sire_token and self.l10n_pe_sire_token_expires_at:
            cache.token = self.l10n_pe_sire_token
            expires = self.l10n_pe_sire_token_expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            cache.expires_at = expires

        return SunatSireRestClient(
            client_id=self.l10n_pe_sire_client_id,
            client_secret=self.l10n_pe_sire_client_secret,
            ruc=self.vat.strip(),
            environment=self.l10n_pe_edi_environment or "beta",
            token_cache=cache,
        )
