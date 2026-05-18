# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Matcher de propuesta SIRE RCE → account.move."""

import logging
from decimal import Decimal

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

SIRE_MATCH_STATUS = [
    ("not_matched", "No conciliado"),
    ("matched", "Conciliado"),
    ("discrepancy", "Conciliado con diferencias"),
    ("missing_in_odoo", "Falta en Odoo"),
]


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_pe_sire_match_status = fields.Selection(
        selection=SIRE_MATCH_STATUS,
        string="Estado conciliación SIRE",
        readonly=True,
        copy=False,
    )
    l10n_pe_sire_match_period = fields.Char(
        string="Período SIRE último match",
        readonly=True,
        copy=False,
    )
    l10n_pe_sire_match_diff = fields.Text(
        string="Diferencias SIRE",
        readonly=True,
        copy=False,
        help="Resumen de las discrepancias detectadas entre la propuesta SUNAT "
        "y el asiento Odoo (importes, fechas).",
    )

    def _l10n_pe_sire_reconcile_proposal(
        self, lines, period_yyyymm: str, tolerance: Decimal = Decimal("0.01")
    ) -> dict:
        """Compara una lista de RceProposalLine vs los in_invoice del período.

        Recorre cada línea de la propuesta SUNAT, busca un account.move que
        encaje por (vat del proveedor, serie-número, fecha emisión) y compara
        importes. Marca los moves matcheados y devuelve un resumen.

        Returns:
            dict {'matched': N, 'discrepancy': N, 'missing_in_odoo': N,
                  'unmatched_proposals': [...], 'odoo_only': [...]}
        """
        Move = self.env["account.move"]
        company = self.env.company
        results = {
            "matched": 0,
            "discrepancy": 0,
            "missing_in_odoo": 0,
            "unmatched_proposals": [],
            "odoo_only": [],
        }
        matched_move_ids = set()

        for prop in lines:
            serie_num = f"{prop.serie}-{prop.number}".strip("-")
            domain = [
                ("company_id", "=", company.id),
                ("move_type", "=", "in_invoice"),
                ("partner_id.vat", "=", prop.supplier_doc_number),
                "|",
                ("name", "=", serie_num),
                ("ref", "=", serie_num),
            ]
            candidate = Move.search(domain, limit=1)
            if not candidate:
                results["missing_in_odoo"] += 1
                results["unmatched_proposals"].append(
                    {
                        "supplier_vat": prop.supplier_doc_number,
                        "serie_number": serie_num,
                        "total": str(prop.total),
                        "issue_date": prop.issue_date.isoformat() if prop.issue_date else "",
                    }
                )
                continue
            matched_move_ids.add(candidate.id)
            diffs = self._l10n_pe_sire_compare(candidate, prop, tolerance)
            if diffs:
                candidate.write(
                    {
                        "l10n_pe_sire_match_status": "discrepancy",
                        "l10n_pe_sire_match_period": period_yyyymm,
                        "l10n_pe_sire_match_diff": "\n".join(diffs),
                    }
                )
                results["discrepancy"] += 1
            else:
                candidate.write(
                    {
                        "l10n_pe_sire_match_status": "matched",
                        "l10n_pe_sire_match_period": period_yyyymm,
                        "l10n_pe_sire_match_diff": False,
                    }
                )
                results["matched"] += 1

        # Detect: facturas Odoo del período sin línea correspondiente en propuesta
        year = int(period_yyyymm[:4])
        month = int(period_yyyymm[4:])
        from datetime import date as _d

        date_from = _d(year, month, 1)
        date_to = _d(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        odoo_period = Move.search(
            [
                ("company_id", "=", company.id),
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<", date_to),
            ]
        )
        for m in odoo_period:
            if m.id in matched_move_ids:
                continue
            m.write(
                {
                    "l10n_pe_sire_match_status": "not_matched",
                    "l10n_pe_sire_match_period": period_yyyymm,
                    "l10n_pe_sire_match_diff": _("Sin contrapartida en propuesta SUNAT."),
                }
            )
            results["odoo_only"].append(
                {"id": m.id, "name": m.name or m.ref or "", "total": str(m.amount_total)}
            )

        return results

    @staticmethod
    def _l10n_pe_sire_compare(move, prop, tolerance: Decimal) -> list[str]:
        """Devuelve lista de strings describiendo discrepancias."""
        diffs = []
        # Comparación total
        if abs(Decimal(str(move.amount_total)) - prop.total) > tolerance:
            diffs.append(f"Total Odoo={move.amount_total} vs SUNAT={prop.total}")
        # Fecha emisión
        if move.invoice_date and prop.issue_date and move.invoice_date != prop.issue_date:
            diffs.append(f"Fecha emisión Odoo={move.invoice_date} vs SUNAT={prop.issue_date}")
        return diffs
