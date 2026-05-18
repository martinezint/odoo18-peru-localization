# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import api, fields, models

PERCEPTION_REGIME_SELECTION = [
    ("01", "Venta Interna (2%)"),
    ("02", "Combustible (1%)"),
    ("03", "Importación (5%)"),
]


class L10nPePerception(models.Model):
    _name = "l10n.pe.perception"
    _description = "Comprobante de Percepción (Perú, SUNAT cat 01 tipo 40)"
    _order = "issue_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Número",
        required=True,
        copy=False,
        help="Serie + correlativo, ej. 'P001-1'.",
    )
    issue_date = fields.Date(
        string="Fecha de emisión",
        required=True,
        default=fields.Date.context_today,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Sujeto Percibido (Cliente)",
        required=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    regime_code = fields.Selection(
        selection=PERCEPTION_REGIME_SELECTION,
        string="Régimen Percepción",
        required=True,
        default="01",
    )
    regime_percent = fields.Float(
        string="% Percepción",
        required=True,
        default=2.0,
        digits=(5, 2),
    )
    note_amount_in_words = fields.Char(string="Importe en letras")

    line_ids = fields.One2many(
        comodel_name="l10n.pe.perception.line",
        inverse_name="perception_id",
        string="Documentos percibidos",
    )

    total_perception_amount = fields.Monetary(
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total_cashed = fields.Monetary(
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("posted", "Posteado"),
            ("cancel", "Cancelado"),
        ],
        default="draft",
        required=True,
        copy=False,
    )

    edi_document_id = fields.Many2one(
        comodel_name="l10n.pe.edi.document",
        string="Documento EDI",
        readonly=True,
        copy=False,
    )

    _sql_constraints = [
        (
            "name_company_unique",
            "UNIQUE(name, company_id)",
            "Ya existe una percepción con ese número en esta empresa.",
        ),
    ]

    @api.depends("line_ids.perception_amount", "line_ids.total_cashed")
    def _compute_totals(self):
        for rec in self:
            rec.total_perception_amount = sum(rec.line_ids.mapped("perception_amount"))
            rec.total_cashed = sum(rec.line_ids.mapped("total_cashed"))


class L10nPePerceptionLine(models.Model):
    _name = "l10n.pe.perception.line"
    _description = "Línea de percepción (documento de origen)"
    _order = "sequence, id"

    perception_id = fields.Many2one(
        comodel_name="l10n.pe.perception",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    currency_id = fields.Many2one(related="perception_id.currency_id", store=True)

    doc_type_code = fields.Selection(
        selection=[
            ("01", "Factura"),
            ("03", "Boleta"),
            ("08", "Nota de Débito"),
        ],
        string="Tipo Doc",
        required=True,
        default="01",
    )
    doc_serie_number = fields.Char(string="Serie-Número", required=True)
    doc_issue_date = fields.Date(string="Fecha emisión", required=True)
    doc_total_amount = fields.Monetary(
        string="Importe Total",
        required=True,
        currency_field="currency_id",
    )

    paid_amount = fields.Monetary(
        string="Pagado",
        required=True,
        currency_field="currency_id",
    )
    paid_date = fields.Date(string="Fecha pago", required=True)

    perception_amount = fields.Monetary(
        string="Percibido",
        required=True,
        currency_field="currency_id",
    )
    perception_date = fields.Date(string="Fecha percepción", required=True)
    total_cashed = fields.Monetary(
        string="Total cobrado",
        compute="_compute_cashed",
        store=True,
        currency_field="currency_id",
        help="paid_amount + perception_amount",
    )

    exchange_rate = fields.Float(default=1.0, digits=(12, 3))
    exchange_rate_date = fields.Date()

    @api.depends("paid_amount", "perception_amount")
    def _compute_cashed(self):
        for rec in self:
            rec.total_cashed = (rec.paid_amount or 0.0) + (rec.perception_amount or 0.0)
