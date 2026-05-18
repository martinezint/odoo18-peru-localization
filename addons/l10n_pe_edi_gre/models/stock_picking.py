# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64
import logging
from datetime import datetime
from decimal import Decimal

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.gre_remitente_ubl_builder import (
    TRANSPORT_MODE_PRIVATE,
    TRANSPORT_MODE_PUBLIC,
    Address,
    DespatchLine,
    GreRemitente,
    GreRemitenteUblBuilder,
    Party,
    ShipmentStage,
)

_logger = logging.getLogger(__name__)


MOTIVO_TRASLADO_SELECTION = [
    ("01", "01 - Venta"),
    ("02", "02 - Compra"),
    ("04", "04 - Traslado entre establecimientos del mismo contribuyente"),
    ("08", "08 - Importación"),
    ("09", "09 - Exportación"),
    ("13", "13 - Otros"),
    ("14", "14 - Venta sujeta a confirmación"),
    ("18", "18 - Traslado emisor itinerante"),
]


TRANSPORT_MODE_SELECTION = [
    (TRANSPORT_MODE_PUBLIC, "01 - Transporte público"),
    (TRANSPORT_MODE_PRIVATE, "02 - Transporte privado"),
]


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # ─── GRE: datos del traslado ──────────────────────────────────

    l10n_pe_gre_motivo_traslado = fields.Selection(
        selection=MOTIVO_TRASLADO_SELECTION,
        string="Motivo del traslado (cat 20)",
    )
    l10n_pe_gre_motivo_descripcion = fields.Char(
        string="Descripción motivo",
        help="Texto libre que acompaña el código del motivo (Information).",
    )
    l10n_pe_gre_transport_mode = fields.Selection(
        selection=TRANSPORT_MODE_SELECTION,
        string="Modalidad de transporte",
        default=TRANSPORT_MODE_PRIVATE,
    )
    l10n_pe_gre_carrier_id = fields.Many2one(
        comodel_name="res.partner",
        string="Transportista",
        help="Solo para transporte público. Para transporte privado, el "
        "remitente actúa como transportista.",
    )
    l10n_pe_gre_license_plate = fields.Char(
        string="Placa del vehículo",
        size=10,
    )
    l10n_pe_gre_driver_doc_type = fields.Selection(
        selection=[
            ("1", "DNI"),
            ("4", "CE"),
            ("7", "Pasaporte"),
        ],
        string="Tipo doc conductor",
        default="1",
    )
    l10n_pe_gre_driver_doc_number = fields.Char(
        string="N° doc conductor",
        size=12,
    )

    # Ubigeos origen/destino
    l10n_pe_gre_origin_ubigeo = fields.Char(
        string="Ubigeo origen",
        size=6,
        help="6 dígitos INEI/SUNAT. Ej. 150122 (Miraflores).",
    )
    l10n_pe_gre_destination_ubigeo = fields.Char(
        string="Ubigeo destino",
        size=6,
    )
    l10n_pe_gre_origin_street = fields.Char(string="Dirección origen")
    l10n_pe_gre_destination_street = fields.Char(string="Dirección destino")

    l10n_pe_gre_gross_weight = fields.Float(
        string="Peso bruto (kg)",
        digits=(12, 3),
    )
    l10n_pe_gre_total_packages = fields.Integer(
        string="N° de bultos",
        default=1,
    )

    # Documento EDI asociado (linkea con l10n.pe.edi.document)
    l10n_pe_gre_edi_document_id = fields.Many2one(
        comodel_name="l10n.pe.edi.document",
        string="Documento EDI GRE",
        readonly=True,
        copy=False,
    )

    # ─── Validaciones suaves ──────────────────────────────────────

    @api.constrains("l10n_pe_gre_origin_ubigeo", "l10n_pe_gre_destination_ubigeo")
    def _check_ubigeos_format(self):
        for rec in self:
            for fname, val in [
                ("l10n_pe_gre_origin_ubigeo", rec.l10n_pe_gre_origin_ubigeo),
                ("l10n_pe_gre_destination_ubigeo", rec.l10n_pe_gre_destination_ubigeo),
            ]:
                if val and (len(val) != 6 or not val.isdigit()):
                    raise UserError(
                        _("Ubigeo %s debe ser 6 dígitos numéricos (INEI/SUNAT).") % fname
                    )

    # ─── Acción: generar GRE Remitente UBL ────────────────────────

    def action_l10n_pe_gre_generate(self):
        """Construye el DespatchAdvice UBL y lo firma con el cert de la empresa."""
        for picking in self:
            picking._l10n_pe_gre_generate_one()
        return True

    def _l10n_pe_gre_generate_one(self):
        self.ensure_one()
        self._l10n_pe_gre_validate_required()

        # 1. Mapear stock.picking → GreRemitente
        gre = self._l10n_pe_gre_build_dataclass()

        # 2. Construir UBL
        builder = GreRemitenteUblBuilder()
        root = builder.build(gre)

        # 3. Firmar
        signer = self.company_id._get_l10n_pe_edi_signer()
        signer.sign(root, signature_id="SignatureSP")

        from lxml import etree

        xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=False)

        # 4. Persistir en l10n.pe.edi.document
        # Como no hay account.move, creamos un doc sin move_id... pero el modelo
        # tiene move_id required. Workaround: necesitamos un move. Por ahora
        # usamos el campo de origen del picking si tiene un sale_id con account_move,
        # o lanzamos un error.
        filename = self._l10n_pe_gre_build_filename()
        doc_vals = {
            "name": filename,
            "xml_signed": base64.b64encode(xml_bytes),
            "state": "signed",
            "last_action_at": fields.Datetime.now(),
        }
        # GRE no requiere account.move pero el modelo lo exige; usamos
        # placeholder o fallamos limpio.
        # TODO v2: hacer move_id opcional en l10n.pe.edi.document.
        ref_move = self._l10n_pe_gre_find_related_move()
        if ref_move:
            doc_vals["move_id"] = ref_move.id
            doc = self.env["l10n.pe.edi.document"].create(doc_vals)
            self.l10n_pe_gre_edi_document_id = doc.id
            _logger.info("GRE Remitente generado para %s → %s", self.name, doc.name)
            return doc
        else:
            raise UserError(
                _(
                    "GRE requiere un account.move asociado (limitación temporal). "
                    "Crea una factura para este picking primero, o vincula manualmente."
                )
            )

    def _l10n_pe_gre_validate_required(self):
        self.ensure_one()
        missing = []
        if not self.company_id.vat:
            missing.append("RUC empresa")
        if not self.partner_id or not self.partner_id.vat:
            missing.append("RUC destinatario (partner_id.vat)")
        if not self.l10n_pe_gre_motivo_traslado:
            missing.append("motivo de traslado")
        if not self.l10n_pe_gre_transport_mode:
            missing.append("modalidad de transporte")
        if not self.l10n_pe_gre_license_plate:
            missing.append("placa del vehículo")
        if not self.l10n_pe_gre_driver_doc_number:
            missing.append("documento del conductor")
        if not self.l10n_pe_gre_origin_ubigeo:
            missing.append("ubigeo origen")
        if not self.l10n_pe_gre_destination_ubigeo:
            missing.append("ubigeo destino")
        if missing:
            raise UserError(
                _("Faltan datos obligatorios para GRE en el picking %s: %s")
                % (self.name, ", ".join(missing))
            )

    def _l10n_pe_gre_build_dataclass(self) -> GreRemitente:
        self.ensure_one()
        co = self.company_id
        partner = self.partner_id

        supplier = Party(
            ruc=(co.vat or "").strip(),
            doc_type_code="6",
            legal_name=co.name,
        )
        customer = Party(
            ruc=(partner.vat or "").strip(),
            doc_type_code=(
                partner.l10n_latam_identification_type_id.l10n_pe_vat_code
                if partner.l10n_latam_identification_type_id
                else "6"
            ),
            legal_name=partner.name,
        )

        # Transportista: para público, el del campo carrier_id; para privado,
        # el emisor.
        if self.l10n_pe_gre_transport_mode == TRANSPORT_MODE_PUBLIC and self.l10n_pe_gre_carrier_id:
            carrier_ruc = (self.l10n_pe_gre_carrier_id.vat or "").strip()
            carrier_name = self.l10n_pe_gre_carrier_id.name
        else:
            carrier_ruc = supplier.ruc
            carrier_name = supplier.legal_name

        stage = ShipmentStage(
            transport_mode=self.l10n_pe_gre_transport_mode or TRANSPORT_MODE_PRIVATE,
            transit_start_date=self.scheduled_date.date() if self.scheduled_date else None,
            carrier_ruc=carrier_ruc,
            carrier_name=carrier_name,
            license_plate=self.l10n_pe_gre_license_plate or "",
            driver_doc_type=self.l10n_pe_gre_driver_doc_type or "1",
            driver_doc_number=self.l10n_pe_gre_driver_doc_number or "",
        )

        # Líneas desde stock.move
        lines = []
        for i, move in enumerate(self.move_ids, start=1):
            lines.append(
                DespatchLine(
                    line_id=i,
                    description=move.product_id.display_name or "Producto",
                    quantity=Decimal(str(move.product_uom_qty)),
                    unit_code="NIU",
                    item_code=move.product_id.default_code or "",
                )
            )

        # Serie + número del picking name (best effort)
        serie_number = (self.name or "T001-1").replace("/", "-").lstrip("-")

        now = datetime.now()
        return GreRemitente(
            serie_number=serie_number,
            issue_date=fields.Date.today(),
            issue_time=now.time().replace(microsecond=0),
            supplier=supplier,
            customer=customer,
            motivo_traslado=self.l10n_pe_gre_motivo_traslado,
            motivo_descripcion=self.l10n_pe_gre_motivo_descripcion or "",
            gross_weight=Decimal(str(self.l10n_pe_gre_gross_weight or 0)),
            total_packages=self.l10n_pe_gre_total_packages or 1,
            stage=stage,
            origin=Address(
                ubigeo=self.l10n_pe_gre_origin_ubigeo or "",
                street=self.l10n_pe_gre_origin_street or "",
            ),
            delivery=Address(
                ubigeo=self.l10n_pe_gre_destination_ubigeo or "",
                street=self.l10n_pe_gre_destination_street or "",
            ),
            lines=lines,
        )

    def _l10n_pe_gre_build_filename(self) -> str:
        ruc = (self.company_id.vat or "").strip()
        ref = (self.name or "").replace("/", "-").lstrip("-")
        return f"{ruc}-09-{ref}.xml"

    def _l10n_pe_gre_find_related_move(self):
        """Busca un account.move asociado al picking (vía sale_order o purchase).

        Limitación de la primera versión: el modelo l10n.pe.edi.document requiere
        move_id obligatorio. Para GRE puro (sin factura), necesitaremos relajar
        ese constraint en una iteración futura.
        """
        self.ensure_one()
        # Intento 1: sale_order asociado
        if hasattr(self, "sale_id") and self.sale_id:
            moves = self.sale_id.invoice_ids.filtered(lambda m: m.state == "posted")
            if moves:
                return moves[0]
        # Intento 2: cualquier move del partner reciente
        return False
