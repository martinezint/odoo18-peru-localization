# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import logging

from lxml import etree
from odoo import models

_logger = logging.getLogger(__name__)


NS_DS = "http://www.w3.org/2000/09/xmldsig#"


class L10nPeEdiDocument(models.Model):
    _inherit = "l10n.pe.edi.document"

    def _extract_signature_value(self) -> str:
        """Extrae ds:SignatureValue del xml_signed (en base64). Vacío si no hay firma.

        SUNAT RS 097-2012 pide hash en el QR; SignatureValue cumple (es la firma
        digital del documento). Algunos lo truncan a 40 chars; nosotros enviamos
        completo y la representación impresa decide cómo truncarlo.
        """
        self.ensure_one()
        if not self.xml_signed:
            return ""
        try:
            xml_bytes = base64.b64decode(self.xml_signed)
            root = etree.fromstring(xml_bytes)
            sig = root.find(f".//{{{NS_DS}}}SignatureValue")
            if sig is not None and sig.text:
                return sig.text.strip().replace("\n", "").replace("\r", "")
        except Exception:
            _logger.exception("Failed to extract SignatureValue from edi document %s", self.id)
        return ""
