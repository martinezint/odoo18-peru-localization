# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # ─── Cuentas destino por función (clase 9 PCGE) ───────────────────
    l10n_pe_dest_admin_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cta destino — Administración (94)",
        domain="[('code', '=like', '94%'), ('company_ids', 'in', id)]",
        help="Cuenta de clase 9 para gastos administrativos.",
    )
    l10n_pe_dest_sales_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cta destino — Ventas (95)",
        domain="[('code', '=like', '95%'), ('company_ids', 'in', id)]",
    )
    l10n_pe_dest_production_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cta destino — Producción (92)",
        domain="[('code', '=like', '92%'), ('company_ids', 'in', id)]",
    )
    l10n_pe_dest_distribution_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cta destino — Distribución (93)",
        domain="[('code', '=like', '93%'), ('company_ids', 'in', id)]",
    )

    # ─── Cuenta puente clase 79 ───────────────────────────────────────
    l10n_pe_transfer_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cta 79 — Cargas imputables a costos/gastos",
        domain="[('code', '=like', '79%'), ('company_ids', 'in', id)]",
        help="Cuenta puente que equilibra el doble apunte clase 6 ↔ clase 9. "
        "Habitualmente '791 Cargas imputables a cuentas de costos y gastos'.",
    )

    # ─── Flags ────────────────────────────────────────────────────────
    l10n_pe_auto_double_entry = fields.Boolean(
        string="Generar doble apunte 6↔9 automáticamente al postear",
        default=True,
        help="Si está activo, al postear un account.move con líneas en cuentas "
        "de clase 6 (gastos por naturaleza), Odoo genera automáticamente el "
        "asiento contrapartida en clase 9 + 79.",
    )
    l10n_pe_default_destination_type = fields.Selection(
        selection=[
            ("admin", "Administración (94)"),
            ("sales", "Ventas (95)"),
            ("production", "Producción (92)"),
            ("distribution", "Distribución (93)"),
        ],
        default="admin",
        string="Función destino por defecto",
        help="Función a la que se imputarán los gastos cuando el usuario no "
        "especifique una explícitamente en el move.",
    )
