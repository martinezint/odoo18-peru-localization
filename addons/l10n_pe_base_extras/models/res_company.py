# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models

REGIMEN_TRIBUTARIO_SELECTION = [
    ("general", "Régimen General"),
    ("mype", "Régimen MYPE Tributario"),
    ("rer", "Régimen Especial de Renta (RER)"),
    ("nrus", "Nuevo Régimen Único Simplificado (NRUS)"),
]


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_pe_regimen_tributario = fields.Selection(
        selection=REGIMEN_TRIBUTARIO_SELECTION,
        string="Régimen Tributario",
        default="general",
        help="Régimen tributario SUNAT de la empresa. Afecta los tipos de comprobante "
        "permitidos, las plantillas de impuestos aplicables y los libros "
        "electrónicos que la empresa debe presentar (PLE/SIRE).",
    )
    l10n_pe_apisnet_token = fields.Char(
        string="Token apis.net.pe",
        help="Token de autenticación para consultar RUC/DNI online en apis.net.pe. "
        "Obtenlo gratis en https://apis.net.pe/api-token.",
        groups="base.group_system",
    )
