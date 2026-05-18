# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import logging
from decimal import Decimal

from odoo import models

from ..services.qr_generator import build_qr_data, build_qr_png_bytes

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_pe_edi_qr_data(self) -> str:
        """Devuelve el string para el QR según RS 097-2012.

        Si el move no tiene un l10n.pe.edi.document, devuelve string vacío.
        """
        self.ensure_one()
        doc = self.l10n_pe_edi_document_id
        if not doc:
            return ""

        # Extraer serie + número de move.name
        serie, number = "", ""
        if self.name:
            for sep in ("/", "-"):
                if sep in self.name:
                    parts = self.name.split(sep, 1)
                    serie, number = parts[0], parts[1]
                    break

        # Tipo documento SUNAT (cat 01)
        doc_type_code = "07" if self.move_type == "out_refund" else "01"

        # Tipo doc del cliente (cat 06)
        partner = self.partner_id
        cust_type = "0"
        if partner.l10n_latam_identification_type_id and \
                partner.l10n_latam_identification_type_id.l10n_pe_vat_code:
            cust_type = partner.l10n_latam_identification_type_id.l10n_pe_vat_code

        return build_qr_data(
            ruc=(self.company_id.vat or "").strip(),
            doc_type_code=doc_type_code,
            serie=serie,
            number=number,
            igv=Decimal(str(self.amount_tax or 0)),
            total=Decimal(str(self.amount_total or 0)),
            issue_date=self.invoice_date or self.date,
            customer_doc_type_code=cust_type,
            customer_doc_number=(partner.vat or "").strip(),
            hash_value=doc._extract_signature_value(),
        )

    def _l10n_pe_edi_qr_png_base64(self) -> str:
        """Devuelve el QR como base64 PNG, listo para embebir en QWeb con
        <img t-attf-src="data:image/png;base64,#{...}"/>.
        """
        self.ensure_one()
        data = self._l10n_pe_edi_qr_data()
        if not data:
            return ""
        png_bytes = build_qr_png_bytes(data)
        return base64.b64encode(png_bytes).decode("ascii")
