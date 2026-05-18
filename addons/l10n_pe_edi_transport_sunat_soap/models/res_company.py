# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_pe_edi_sol_user = fields.Char(
        string="Usuario SOL (SUNAT)",
        groups="base.group_system",
        help="Usuario secundario SOL emisor electrónico. Para BETA usar 'MODDATOS'.",
    )
    l10n_pe_edi_sol_password = fields.Char(
        string="Password SOL",
        groups="base.group_system",
        help="Password del usuario SOL. Para BETA usar 'MODDATOS'.",
    )

    def _get_l10n_pe_sunat_soap_client(self):
        """Devuelve un SunatBillService autenticado con los datos de la empresa."""
        self.ensure_one()
        if not self.vat:
            raise UserError(_("La empresa %s no tiene RUC configurado.") % self.name)
        if not self.l10n_pe_edi_sol_user or not self.l10n_pe_edi_sol_password:
            raise UserError(
                _(
                    "Faltan credenciales SOL para SUNAT en la empresa %s. "
                    "Configúralas en Ajustes → Empresa → Usuario/Password SOL."
                )
                % self.name
            )
        from ..services.sunat_soap import SunatBillService

        return SunatBillService(
            ruc=self.vat.strip(),
            sol_user=self.l10n_pe_edi_sol_user.strip(),
            sol_password=self.l10n_pe_edi_sol_password,
            environment=self.l10n_pe_edi_environment or "beta",
        )
