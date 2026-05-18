# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Modelo standalone GRE Transportista (SUNAT cat 01 tipo 31).

A diferencia de la GRE Remitente que se ata a stock.picking (el remitente
mueve su propio stock), el transportista NO posee la carga; simplemente
emite un documento que respalda el servicio de transporte que ofrece.

Por eso este modelo es independiente: el contador de la empresa
transportista lo crea manualmente (o desde una orden de servicio futura).
"""

import base64
import logging
import zipfile
from datetime import time
from decimal import Decimal
from io import BytesIO

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.gre_transportista_ubl_builder import (
    Address,
    DespatchLine,
    GreTransportista,
    GreTransportistaUblBuilder,
    Party,
    RelatedRemitenteDoc,
)

_logger = logging.getLogger(__name__)


class L10nPeGreTransportista(models.Model):
    _name = "l10n.pe.gre.transportista"
    _description = "Guía de Remisión Electrónica Transportista (cat 01 tipo 31)"
    _inherit = ["mail.thread"]
    _order = "issue_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Serie-Número",
        required=True,
        copy=False,
        help="Ej. 'V001-1'. Serie 'V' por convención SUNAT para Transportista.",
    )
    issue_date = fields.Date(
        string="Fecha emisión",
        required=True,
        default=fields.Date.context_today,
    )
    issue_time = fields.Float(
        string="Hora emisión",
        default=12.0,
        help="Hora del día en notación decimal (12.5 = 12:30).",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    # ─── Partes ──────────────────────────────────────────────────────
    remitente_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Remitente (cliente del servicio)",
        required=True,
        help="Empresa que contrató el servicio de transporte.",
    )
    destinatario_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Destinatario",
        required=True,
    )

    # ─── Referencia GRE Remitente origen ─────────────────────────────
    related_remitente_serie_number = fields.Char(
        string="GRE Remitente origen (serie-número)",
        required=True,
        help="Documento GRE Remitente que respalda esta guía de transporte.",
    )

    # ─── Carga ────────────────────────────────────────────────────────
    gross_weight = fields.Float(
        string="Peso bruto (KG)",
        required=True,
        digits=(12, 3),
    )
    total_packages = fields.Integer(default=1, required=True)
    split_consignment = fields.Boolean(string="Envío fraccionado")

    # ─── Vehículo + conductor ────────────────────────────────────────
    license_plate = fields.Char(string="Placa vehículo", required=True, size=10)
    driver_doc_type = fields.Selection(
        selection=[("1", "DNI"), ("4", "CE"), ("7", "Pasaporte")],
        default="1",
        required=True,
    )
    driver_doc_number = fields.Char(string="Documento conductor", required=True)
    transit_start_date = fields.Date(
        string="Inicio del traslado",
        default=fields.Date.context_today,
        required=True,
    )

    # ─── Direcciones ──────────────────────────────────────────────────
    origin_ubigeo = fields.Char(string="Ubigeo origen", size=6, required=True)
    origin_street = fields.Char(string="Dirección origen")
    destination_ubigeo = fields.Char(string="Ubigeo destino", size=6, required=True)
    destination_street = fields.Char(string="Dirección destino")

    # ─── Líneas (ítems transportados) ─────────────────────────────────
    line_ids = fields.One2many(
        comodel_name="l10n.pe.gre.transportista.line",
        inverse_name="gre_id",
        string="Ítems",
    )

    # ─── EDI ──────────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("generated", "XML generado"),
            ("sent", "Enviado SUNAT"),
            ("accepted", "Aceptado"),
            ("error", "Error"),
        ],
        default="draft",
        tracking=True,
    )
    xml_signed = fields.Binary(readonly=True, attachment=True)
    gre_ticket = fields.Char(readonly=True)
    error_message = fields.Text(readonly=True)

    _sql_constraints = [
        (
            "name_company_unique",
            "UNIQUE(name, company_id)",
            "Ya existe una GRE Transportista con ese número en esta empresa.",
        ),
    ]

    # ─── Validaciones ─────────────────────────────────────────────────

    def _validate_required(self):
        for rec in self:
            missing = []
            if (
                not rec.origin_ubigeo
                or len(rec.origin_ubigeo) != 6
                or not rec.origin_ubigeo.isdigit()
            ):
                missing.append(_("Ubigeo origen (6 dígitos)"))
            if (
                not rec.destination_ubigeo
                or len(rec.destination_ubigeo) != 6
                or not rec.destination_ubigeo.isdigit()
            ):
                missing.append(_("Ubigeo destino (6 dígitos)"))
            if not rec.license_plate:
                missing.append(_("Placa del vehículo"))
            if not rec.driver_doc_number:
                missing.append(_("Documento del conductor"))
            if not rec.related_remitente_serie_number:
                missing.append(_("Referencia GRE Remitente"))
            if not rec.line_ids:
                missing.append(_("Al menos 1 ítem"))
            if not rec.company_id.vat:
                missing.append(_("RUC del transportista (empresa)"))
            if missing:
                raise UserError(_("Faltan datos obligatorios:\n - %s") % "\n - ".join(missing))

    # ─── Generar UBL ──────────────────────────────────────────────────

    def _build_dataclass(self) -> GreTransportista:
        self.ensure_one()
        hours = int(self.issue_time)
        minutes = int((self.issue_time - hours) * 60)
        return GreTransportista(
            serie_number=self.name,
            issue_date=self.issue_date,
            issue_time=time(hours, minutes, 0),
            transportista=Party(
                ruc=self.company_id.vat or "",
                doc_type_code="6",
                legal_name=self.company_id.name,
            ),
            remitente=Party(
                ruc=self.remitente_partner_id.vat or "",
                doc_type_code="6"
                if (self.remitente_partner_id.vat and len(self.remitente_partner_id.vat) == 11)
                else "1",
                legal_name=self.remitente_partner_id.name,
            ),
            destinatario=Party(
                ruc=self.destinatario_partner_id.vat or "",
                doc_type_code="6"
                if (
                    self.destinatario_partner_id.vat and len(self.destinatario_partner_id.vat) == 11
                )
                else "1",
                legal_name=self.destinatario_partner_id.name,
            ),
            related_remitente_doc=RelatedRemitenteDoc(
                doc_type_code="09",
                serie_number=self.related_remitente_serie_number,
            ),
            gross_weight=Decimal(str(self.gross_weight)),
            total_packages=self.total_packages,
            split_consignment=self.split_consignment,
            license_plate=self.license_plate,
            driver_doc_type=self.driver_doc_type,
            driver_doc_number=self.driver_doc_number,
            transit_start_date=self.transit_start_date,
            origin=Address(ubigeo=self.origin_ubigeo, street=self.origin_street or ""),
            delivery=Address(ubigeo=self.destination_ubigeo, street=self.destination_street or ""),
            lines=[
                DespatchLine(
                    line_id=idx + 1,
                    description=ln.description,
                    quantity=Decimal(str(ln.quantity)),
                    unit_code=ln.unit_code,
                    item_code=ln.item_code or "",
                )
                for idx, ln in enumerate(self.line_ids)
            ],
        )

    def action_generate_xml(self):
        for rec in self:
            rec._validate_required()
            dc = rec._build_dataclass()
            xml = GreTransportistaUblBuilder().build_xml_bytes(dc)
            # Firmar usando el signer compartido
            signer = rec.company_id._get_l10n_pe_edi_signer()
            signed = signer.sign(xml)
            rec.xml_signed = base64.b64encode(signed)
            rec.state = "generated"
        return True

    def action_generate_and_send(self):
        for rec in self:
            rec.action_generate_xml()
            if not rec.xml_signed:
                continue
            client = rec.company_id._get_l10n_pe_gre_rest_client()
            xml_bytes = base64.b64decode(rec.xml_signed)
            xml_filename = f"{rec.company_id.vat}-31-{rec.name}.xml"
            zip_filename = xml_filename.replace(".xml", ".zip")
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(xml_filename, xml_bytes)
            num_doc = f"31-{rec.name}"
            try:
                ticket = client.send_gre(num_doc, zip_filename, buf.getvalue())
            except Exception as exc:
                _logger.exception("GRE Transportista send_gre fallo %s", rec.name)
                rec.write({"state": "error", "error_message": str(exc)})
                raise UserError(_("SUNAT GRE-Transportista rechazó: %s") % exc) from exc
            rec.write({"gre_ticket": ticket, "state": "sent"})
        return True


class L10nPeGreTransportistaLine(models.Model):
    _name = "l10n.pe.gre.transportista.line"
    _description = "Línea de GRE Transportista (ítem transportado)"
    _order = "sequence, id"

    gre_id = fields.Many2one(
        comodel_name="l10n.pe.gre.transportista",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    description = fields.Char(required=True)
    quantity = fields.Float(required=True, default=1.0)
    unit_code = fields.Char(string="UM (SUNAT)", default="NIU", size=6)
    item_code = fields.Char(string="Código ítem")
