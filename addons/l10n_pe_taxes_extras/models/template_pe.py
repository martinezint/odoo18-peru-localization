# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Contribuciones al chart template 'pe' para retenciones, percepciones,
ICBPER, IVAP y tax groups ISC."""

from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    # ─── Tax Groups extras ────────────────────────────────────────────

    @template("pe", "account.tax.group")
    def _get_pe_tax_group_extras(self):
        return {
            "tax_group_ret_igv": {
                "name": "Retención IGV",
                "sequence": 50,
                "country_id": "base.pe",
            },
            "tax_group_perc_igv": {
                "name": "Percepción IGV",
                "sequence": 51,
                "country_id": "base.pe",
            },
            "tax_group_icbper": {
                "name": "ICBPER",
                "sequence": 52,
                "country_id": "base.pe",
            },
            "tax_group_ivap": {
                "name": "IVAP",
                "sequence": 53,
                "country_id": "base.pe",
            },
            "tax_group_isc_al_valor": {
                "name": "ISC - Al Valor",
                "sequence": 54,
                "country_id": "base.pe",
            },
            "tax_group_isc_especifico": {
                "name": "ISC - Específico",
                "sequence": 55,
                "country_id": "base.pe",
            },
            "tax_group_isc_al_valor_cigarrillos": {
                "name": "ISC - Al Valor Cigarrillos",
                "sequence": 56,
                "country_id": "base.pe",
            },
        }

    # ─── Impuestos extras ─────────────────────────────────────────────

    @template("pe", "account.tax")
    def _get_pe_account_tax_extras(self):
        """Retenciones (compras), percepciones (ventas), ICBPER (ventas, fixed),
        IVAP (ventas). ISC queda como tax groups; tasas específicas se dejan
        para configuración custom porque varían mucho por industria."""
        return {
            # ─── Retenciones IGV (purchase, restan al pago al proveedor) ──
            "tax_ret_igv_1_5": {
                "name": "Retención IGV 1.5%",
                "name@es": "Retención IGV 1.5%",
                "description": "Retención IGV 1.5% sobre comprobantes",
                "invoice_label": "Ret IGV 1.5%",
                "amount": 1.5,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_igv",
                "l10n_pe_tax_kind": "retencion_igv",
                "active": True,
            },
            "tax_ret_igv_3": {
                "name": "Retención IGV 3%",
                "name@es": "Retención IGV 3%",
                "description": "Retención IGV 3% sobre comprobantes (tasa vigente)",
                "invoice_label": "Ret IGV 3%",
                "amount": 3.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_igv",
                "l10n_pe_tax_kind": "retencion_igv",
                "active": True,
            },
            "tax_ret_igv_6": {
                "name": "Retención IGV 6% (histórica)",
                "name@es": "Retención IGV 6% (histórica)",
                "description": "Tasa histórica anterior a 2024",
                "invoice_label": "Ret IGV 6%",
                "amount": 6.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_igv",
                "l10n_pe_tax_kind": "retencion_igv",
                "active": False,  # inactivo por defecto: solo data histórica
            },
            # ─── Percepción IGV (venta, suma al cobro al cliente) ─────────
            "tax_perc_igv_2": {
                "name": "Percepción IGV 2%",
                "name@es": "Percepción IGV 2%",
                "description": "Percepción IGV 2% sobre operación gravada",
                "invoice_label": "Perc IGV 2%",
                "amount": 2.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": "tax_group_perc_igv",
                "l10n_pe_tax_kind": "percepcion_igv",
                "active": True,
            },
            # ─── ICBPER (venta, fixed S/0.50 por unidad de bolsa) ─────────
            "tax_icbper": {
                "name": "ICBPER (Bolsas Plásticas)",
                "name@es": "ICBPER (Bolsas Plásticas)",
                "description": "S/0.50 por bolsa plástica (tarifa vigente 2024-2026)",
                "invoice_label": "ICBPER",
                "amount": 0.50,
                "amount_type": "fixed",
                "type_tax_use": "sale",
                "tax_group_id": "tax_group_icbper",
                "l10n_pe_tax_kind": "icbper",
                "active": True,
            },
            # ─── IVAP (venta, 4% sobre arroz pilado) ──────────────────────
            "tax_ivap_4": {
                "name": "IVAP 4%",
                "name@es": "IVAP 4%",
                "description": "Impuesto a la Venta de Arroz Pilado 4%",
                "invoice_label": "IVAP 4%",
                "amount": 4.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": "tax_group_ivap",
                "l10n_pe_tax_kind": "ivap",
                "active": True,
            },
        }
