# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import logging
from datetime import datetime
from decimal import Decimal

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.ubl_builder import Invoice as UblInvoice
from ..services.ubl_builder import InvoiceLine as UblLine
from ..services.ubl_builder import Party, UblInvoiceBuilder

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_pe_edi_document_id = fields.Many2one(
        comodel_name="l10n.pe.edi.document",
        string="Documento EDI",
        copy=False,
        readonly=True,
    )
    l10n_pe_edi_state = fields.Selection(
        related="l10n_pe_edi_document_id.state",
        string="Estado EDI",
        readonly=True,
        store=False,
    )

    # ─── Acción: generar + firmar UBL ──────────────────────────────────

    def action_l10n_pe_edi_generate(self):
        """Genera el UBL 2.1 y lo firma con el cert de la empresa.

        Idempotente: si ya existe un documento en estado != error/rejected,
        lo reusa (sin re-firmar). Si es nuevo o está en error/rejected, genera
        de cero y firma.
        """
        for move in self:
            move._l10n_pe_edi_generate_one()
        return True

    def _l10n_pe_edi_generate_one(self):
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund"):
            raise UserError(_("Solo facturas de venta tienen EDI en este módulo."))
        if self.state != "posted":
            raise UserError(_("Postear el comprobante antes de generar EDI."))

        doc = self.l10n_pe_edi_document_id
        if doc and doc.state in ("signed", "sent", "accepted"):
            return doc  # ya firmado, no re-firmar

        # 1. Build UBL
        ubl_invoice = self._l10n_pe_edi_to_ubl_invoice()
        builder = UblInvoiceBuilder()
        root = builder.build(ubl_invoice)

        # 2. Sign
        signer = self.company_id._get_l10n_pe_edi_signer()
        signer.sign(root, signature_id="SignatureSP")

        # 3. Persist
        from lxml import etree

        xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=False)

        Doc = self.env["l10n.pe.edi.document"]
        if not doc:
            doc = Doc.create({"move_id": self.id})
            self.l10n_pe_edi_document_id = doc.id

        doc.write(
            {
                "name": doc._build_sunat_filename(self),
                "xml_signed": base64.b64encode(xml_bytes),
                "state": "signed",
                "last_action_at": fields.Datetime.now(),
                "error_message": False,
            }
        )
        _logger.info("EDI generado y firmado para %s: %s", self.name, doc.name)
        return doc

    # ─── Mapping account.move → UBL Invoice ────────────────────────────

    def _l10n_pe_edi_to_ubl_invoice(self) -> UblInvoice:
        """Construye el objeto UblInvoice desde el contexto del account.move.

        v1: asume Factura tipo 01, IGV 18% sobre todas las líneas. Otros tipos
        de operación, exoneraciones, etc., se añaden en iteraciones futuras.
        """
        # Serie + número desde move.name (formato Odoo: "F001/00000001" → "F001-1")
        serie_number = (self.name or "").replace("/", "-").lstrip("-")
        if not serie_number:
            raise UserError(_("El comprobante no tiene nombre/secuencia asignado."))

        now = datetime.now()
        ubl = UblInvoice(
            serie_number=serie_number,
            issue_date=self.invoice_date or fields.Date.today(),
            issue_time=now.time().replace(microsecond=0),
            due_date=self.invoice_date_due,
            currency_code=self.currency_id.name or "PEN",
            supplier=self._l10n_pe_edi_party_from_company(),
            customer=self._l10n_pe_edi_party_from_partner(),
        )

        # Líneas
        total_line = Decimal("0")
        total_igv = Decimal("0")
        for idx, line in enumerate(
            self.invoice_line_ids.filtered(lambda ln: not ln.display_type), start=1
        ):
            line_amt = Decimal(str(line.price_subtotal))
            # Asumimos IGV 18% si las taxes contienen alguno gravado.
            has_igv = any(t.amount == 18 for t in line.tax_ids)
            igv_amt = (
                (line_amt * Decimal("0.18")).quantize(Decimal("0.01")) if has_igv else Decimal("0")
            )
            ubl.lines.append(
                UblLine(
                    line_id=idx,
                    description=line.name or "Sin descripción",
                    quantity=Decimal(str(line.quantity)),
                    unit_code="NIU",
                    unit_price=Decimal(str(line.price_unit)),
                    line_extension_amount=line_amt,
                    igv_amount=igv_amt,
                    igv_affectation_code="10" if has_igv else "30",
                    igv_percentage=Decimal("18") if has_igv else Decimal("0"),
                )
            )
            total_line += line_amt
            total_igv += igv_amt

        ubl.total_line_extension = total_line
        ubl.total_taxed = total_line
        ubl.total_igv = total_igv
        ubl.total_tax_exclusive = total_line
        ubl.total_tax_inclusive = total_line + total_igv
        ubl.total_payable = total_line + total_igv

        return ubl

    def _l10n_pe_edi_party_from_company(self) -> Party:
        co = self.company_id
        return Party(
            ruc=(co.vat or "").strip(),
            doc_type_code="6",  # RUC
            legal_name=co.name,
            address_street=co.street or "",
            address_country="PE",
        )

    def _l10n_pe_edi_party_from_partner(self) -> Party:
        p = self.partner_id
        code = p.l10n_latam_identification_type_id.l10n_pe_vat_code or "6"
        return Party(
            ruc=(p.vat or "").strip(),
            doc_type_code=code,
            legal_name=p.name,
            address_street=p.street or "",
            address_country=(p.country_id.code or "PE"),
        )
