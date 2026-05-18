# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import api, fields, models

RETENTION_REGIME_SELECTION = [
    ("01", "Tasa 3% (Régimen general desde 2014)"),
]


class L10nPeRetention(models.Model):
    _name = "l10n.pe.retention"
    _description = "Comprobante de Retención (Perú, SUNAT cat 01 tipo 20)"
    _order = "issue_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Número",
        required=True,
        copy=False,
        help="Serie + correlativo, ej. 'R001-1'.",
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
        string="Sujeto Retenido (Proveedor)",
        required=True,
        help="Partner al cual se aplica la retención.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    regime_code = fields.Selection(
        selection=RETENTION_REGIME_SELECTION,
        string="Régimen Retención",
        required=True,
        default="01",
    )
    regime_percent = fields.Float(
        string="% Retención",
        required=True,
        default=3.0,
        digits=(5, 2),
    )
    note_amount_in_words = fields.Char(
        string="Importe en letras",
        help="SON ... CON 00/100 SOLES",
    )

    line_ids = fields.One2many(
        comodel_name="l10n.pe.retention.line",
        inverse_name="retention_id",
        string="Documentos retenidos",
    )

    total_retention_amount = fields.Monetary(
        string="Total retenido",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total_paid = fields.Monetary(
        string="Total pagado",
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
            "Ya existe una retención con ese número en esta empresa.",
        ),
    ]

    @api.depends("line_ids.retention_amount", "line_ids.paid_amount")
    def _compute_totals(self):
        for rec in self:
            rec.total_retention_amount = sum(rec.line_ids.mapped("retention_amount"))
            rec.total_paid = sum(rec.line_ids.mapped("paid_amount"))


class L10nPeRetentionLine(models.Model):
    _name = "l10n.pe.retention.line"
    _description = "Línea de retención (documento de origen)"
    _order = "sequence, id"

    retention_id = fields.Many2one(
        comodel_name="l10n.pe.retention",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    currency_id = fields.Many2one(related="retention_id.currency_id", store=True)

    doc_type_code = fields.Selection(
        selection=[
            ("01", "Factura"),
            ("08", "Nota de Débito"),
        ],
        string="Tipo Doc",
        required=True,
        default="01",
    )
    doc_serie_number = fields.Char(
        string="Serie-Número",
        required=True,
        help="Ej. F001-123",
    )
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
        help="Importe pagado (puede ser parcial).",
    )
    paid_date = fields.Date(string="Fecha pago", required=True)

    retention_amount = fields.Monetary(
        string="Retenido",
        required=True,
        currency_field="currency_id",
    )
    retention_date = fields.Date(string="Fecha retención", required=True)
    net_total_cashed = fields.Monetary(
        string="Neto entregado",
        compute="_compute_net",
        store=True,
        currency_field="currency_id",
    )

    exchange_rate = fields.Float(default=1.0, digits=(12, 3))
    exchange_rate_date = fields.Date()

    @api.depends("paid_amount", "retention_amount")
    def _compute_net(self):
        for rec in self:
            rec.net_total_cashed = (rec.paid_amount or 0.0) - (rec.retention_amount or 0.0)
