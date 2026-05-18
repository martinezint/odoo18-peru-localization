# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.cdr_parser import parse_cdr
from ..services.sunat_soap import SunatSoapError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_l10n_pe_edi_send_sunat(self):
        """Envía el XML firmado a SUNAT vía SOAP y actualiza el documento EDI.

        Requiere que el move tenga un l10n_pe_edi_document_id en estado 'signed'.
        Idempotente: si ya está 'accepted', no re-envía.
        """
        for move in self:
            move._l10n_pe_edi_send_sunat_one()
        return True

    def _l10n_pe_edi_send_sunat_one(self):
        self.ensure_one()
        doc = self.l10n_pe_edi_document_id
        if not doc or not doc.xml_signed:
            raise UserError(_(
                "No hay XML firmado para enviar. Primero genera el EDI."
            ))
        if doc.state == "accepted":
            _logger.info("EDI %s ya aceptado por SUNAT; skip.", doc.name)
            return doc

        client = self.company_id._get_l10n_pe_sunat_soap_client()

        # 1. ZIP del XML firmado con nombre <RUC>-<TIPO>-<SERIE>-<NUMERO>.zip
        xml_filename = doc.name  # ej. 20131312955-01-F001-1.xml
        zip_filename = xml_filename.replace(".xml", ".zip")
        xml_bytes = base64.b64decode(doc.xml_signed)
        zip_bytes = client.zip_xml(xml_filename, xml_bytes)

        # 2. sendBill
        try:
            cdr_bytes = client.send_bill(zip_filename, zip_bytes)
        except SunatSoapError as exc:
            doc.write({
                "state": "error",
                "error_message": str(exc),
                "sunat_sent_at": fields.Datetime.now(),
            })
            raise UserError(_("SUNAT rechazó la conexión: %s") % exc) from exc

        # 3. Parse CDR
        cdr = parse_cdr(cdr_bytes)

        # 4. Update doc state según response_code
        if cdr.is_accepted:
            new_state = "accepted"
        elif cdr.is_observed:
            # Observado = aceptado con warnings (notes)
            new_state = "accepted"
        elif cdr.is_rejected:
            new_state = "rejected"
        else:
            new_state = "error"

        cdr_filename = f"R-{xml_filename}"
        doc.write({
            "state": new_state,
            "sunat_cdr": base64.b64encode(cdr_bytes),
            "sunat_cdr_filename": cdr_filename,
            "sunat_response_code": cdr.response_code,
            "sunat_response_description": cdr.description,
            "sunat_sent_at": fields.Datetime.now(),
            "error_message": cdr.description if new_state in ("rejected", "error") else False,
        })
        _logger.info(
            "SUNAT respondió code=%s desc=%r para %s → state=%s",
            cdr.response_code, cdr.description, doc.name, new_state,
        )
        return doc
