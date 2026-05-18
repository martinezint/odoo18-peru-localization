# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import logging
from datetime import date
from decimal import Decimal

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.rc_summary_builder import (
    RcLine,
    RcSummary,
    RcSummaryBuilder,
    RcSupplier,
)

_logger = logging.getLogger(__name__)


class L10nPeRcWizard(models.TransientModel):
    _name = "l10n.pe.rc.wizard"
    _description = "Generador de Resumen Diario de Boletas (RC) SUNAT"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    reference_date = fields.Date(
        string="Fecha de las boletas",
        required=True,
        default=fields.Date.context_today,
        help="Fecha del día cuyas boletas se incluyen en el resumen.",
    )
    issue_date = fields.Date(
        string="Fecha emisión RC",
        required=True,
        default=fields.Date.context_today,
        help="Fecha de envío/emisión del resumen. Habitualmente reference_date + 1 día.",
    )
    correlativo = fields.Integer(
        string="Correlativo del día",
        default=1,
        help="Si en un día se envía más de un resumen, este es el correlativo (001, 002...).",
    )
    sign_xml = fields.Boolean(
        string="Firmar XML",
        default=True,
        help="Si está activo, se firma con el cert XAdES de la empresa. "
             "Desactiva para previsualizar el XML sin firma.",
    )

    boletas_count = fields.Integer(readonly=True)
    edi_document_id = fields.Many2one(
        comodel_name="l10n.pe.edi.document",
        readonly=True,
    )
    xml_data = fields.Binary(readonly=True, attachment=False)
    xml_filename = fields.Char(readonly=True)

    # ─── Action ──────────────────────────────────────────────────

    def action_generate(self):
        self.ensure_one()
        if not self.company_id.vat:
            raise UserError(_("La empresa %s no tiene RUC configurado.") % self.company_id.name)
        boletas = self._search_boletas()
        if not boletas:
            raise UserError(_(
                "No hay boletas posteadas el %s en %s. Nada que resumir."
            ) % (self.reference_date, self.company_id.name))

        summary = self._build_summary(boletas)
        builder = RcSummaryBuilder()
        root = builder.build(summary)

        if self.sign_xml:
            signer = self.company_id._get_l10n_pe_edi_signer()
            signer.sign(root, signature_id="SignatureSP")

        from lxml import etree
        xml_bytes = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=False
        )

        filename = self._build_filename()
        # Creamos un l10n.pe.edi.document sin move_id (RC es agregado, no ligado
        # a un único comprobante). Usamos workaround: tomar el move más reciente
        # como referencia. Si no hay account.move, dejamos doc en None y
        # solo retornamos los bytes para descarga.
        doc = False
        if boletas:
            Doc = self.env["l10n.pe.edi.document"]
            ref_move = boletas[0]
            doc = Doc.create({
                "move_id": ref_move.id,
                "name": filename,
                "xml_signed": base64.b64encode(xml_bytes) if self.sign_xml else False,
                "xml_unsigned": False if self.sign_xml else base64.b64encode(xml_bytes),
                "state": "signed" if self.sign_xml else "draft",
                "last_action_at": fields.Datetime.now(),
            })

        self.write({
            "boletas_count": len(boletas),
            "edi_document_id": doc.id if doc else False,
            "xml_data": base64.b64encode(xml_bytes),
            "xml_filename": filename,
        })

        # Reabre el wizard con el resultado
        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n.pe.rc.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # ─── Helpers ─────────────────────────────────────────────────

    def _search_boletas(self):
        """Busca account.move tipo Boleta (l10n_latam_document_type cat 1 → '03')
        posteados en la empresa el día reference_date.

        Para v1 simplificado: filtramos por move_type='out_invoice' + fecha.
        Cuando l10n_pe_edi integre correctamente l10n_latam_document_type,
        filtraremos también por código '03'.
        """
        return self.env["account.move"].search([
            ("company_id", "=", self.company_id.id),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", "=", self.reference_date),
        ], order="name, id")

    def _build_summary(self, boletas) -> RcSummary:
        co = self.company_id
        supplier = RcSupplier(
            ruc=(co.vat or "").strip(),
            legal_name=co.name,
        )
        serie_number = self._build_filename().replace(".xml", "")
        summary = RcSummary(
            serie_number=serie_number,
            reference_date=self.reference_date,
            issue_date=self.issue_date,
            supplier=supplier,
        )
        for i, move in enumerate(boletas, start=1):
            serie, number = self._split_move_name(move.name or "")
            summary.lines.append(RcLine(
                line_id=i,
                document_type_code="03",
                serie=serie or "B001",
                start_number=number or "0",
                end_number=number or "0",
                total_amount=Decimal(str(move.amount_total or 0)),
                payable_amount=Decimal(str(move.amount_untaxed or 0)),
                tax_amount=Decimal(str(move.amount_tax or 0)),
                currency=move.currency_id.name or "PEN",
            ))
        return summary

    def _build_filename(self) -> str:
        """Nombre SUNAT del RC: <RUC>-RC-<YYYYMMDD>-<CORRELATIVO>.xml.

        Ejemplo: 20131312955-RC-20260518-001.xml
        """
        ruc = (self.company_id.vat or "").strip()
        date_str = self.issue_date.strftime("%Y%m%d")
        corr = f"{self.correlativo:03d}"
        return f"{ruc}-RC-{date_str}-{corr}.xml"

    @staticmethod
    def _split_move_name(name: str) -> tuple[str, str]:
        if not name:
            return ("", "")
        for sep in ("/", "-"):
            if sep in name:
                parts = name.split(sep, 1)
                return (parts[0], parts[1].lstrip("0") or "0")
        return (name, "")
