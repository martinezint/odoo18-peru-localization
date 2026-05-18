# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LIBRO_SELECTION = [
    ("rce", "RCE (Compras)"),
    ("rvie", "RVIE (Ventas e Ingresos)"),
]


PERIOD_STATE_SELECTION = [
    ("draft", "Borrador"),
    ("requested", "Propuesta solicitada"),
    ("ready", "Propuesta lista"),
    ("downloaded", "Descargada"),
    ("accepted", "Aceptada"),
    ("error", "Error"),
]


class L10nPeSirePeriod(models.Model):
    _name = "l10n.pe.sire.period"
    _description = "Período SIRE (RVIE/RCE por mes)"
    _order = "periodo desc, libro"
    _rec_name = "display_name"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    periodo = fields.Char(
        string="Período",
        size=6,
        required=True,
        help="Formato SUNAT YYYYMM, ej. 202604.",
    )
    libro = fields.Selection(
        selection=LIBRO_SELECTION,
        required=True,
    )
    state = fields.Selection(
        selection=PERIOD_STATE_SELECTION,
        default="draft",
        required=True,
        copy=False,
    )

    # Trazabilidad del ticket SUNAT
    ticket = fields.Char(
        string="Ticket SUNAT",
        readonly=True,
        copy=False,
    )
    ticket_requested_at = fields.Datetime(
        string="Solicitado en",
        readonly=True,
        copy=False,
    )
    ticket_last_check_at = fields.Datetime(
        string="Último polling",
        readonly=True,
        copy=False,
    )
    ticket_cod_estado = fields.Char(
        string="Cód. estado SUNAT",
        readonly=True,
        copy=False,
    )
    ticket_descripcion = fields.Char(
        string="Descripción estado",
        readonly=True,
        copy=False,
    )

    # Archivo descargado de la propuesta SUNAT
    file_data = fields.Binary(
        string="Archivo propuesta",
        attachment=True,
        readonly=True,
        copy=False,
    )
    file_name = fields.Char(string="Nombre archivo", readonly=True, copy=False)
    file_url = fields.Char(string="URL SUNAT", readonly=True, copy=False)
    downloaded_at = fields.Datetime(readonly=True, copy=False)

    error_message = fields.Text(readonly=True, copy=False)

    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        (
            "period_unique",
            "UNIQUE(company_id, periodo, libro)",
            "Ya existe un registro SIRE para ese período + libro en esta empresa.",
        ),
    ]

    @api.depends("periodo", "libro", "company_id")
    def _compute_display_name(self):
        for rec in self:
            libro_label = dict(LIBRO_SELECTION).get(rec.libro, "?")
            rec.display_name = f"[{rec.periodo}] {libro_label}"

    @api.constrains("periodo")
    def _check_periodo_format(self):
        for rec in self:
            p = rec.periodo or ""
            if not p or len(p) != 6 or not p.isdigit():
                raise ValidationError(_("Período debe ser YYYYMM (6 dígitos)."))
            year = int(p[:4])
            month = int(p[4:])
            if year < 2018 or year > 2100:
                raise ValidationError(_("Año fuera de rango razonable: %s") % year)
            if not (1 <= month <= 12):
                raise ValidationError(_("Mes inválido: %s") % month)

    # ─── Acciones REST ───────────────────────────────────────────

    def action_request_propuesta(self):
        """Solicita la propuesta SUNAT del período. Pasa de draft→requested."""
        for rec in self:
            rec._request_propuesta_one()
        return True

    def _request_propuesta_one(self):
        self.ensure_one()
        client = self.company_id._get_l10n_pe_sire_rest_client()
        try:
            if self.libro == "rce":
                ticket = client.request_rce_propuesta(self.periodo)
            else:
                ticket = client.request_rvie_propuesta(self.periodo)
        except Exception as exc:
            self.write(
                {
                    "state": "error",
                    "error_message": str(exc),
                    "ticket_requested_at": fields.Datetime.now(),
                }
            )
            raise
        self.write(
            {
                "ticket": ticket,
                "ticket_requested_at": fields.Datetime.now(),
                "state": "requested",
                "error_message": False,
            }
        )

    def action_check_ticket(self):
        """Polling: GET status del ticket. Pasa a 'ready' si TERMINADO."""
        for rec in self:
            rec._check_ticket_one()
        return True

    def _check_ticket_one(self):
        self.ensure_one()
        if not self.ticket:
            return
        client = self.company_id._get_l10n_pe_sire_rest_client()
        status = client.get_ticket_status(self.ticket, libro=self.libro)
        vals = {
            "ticket_last_check_at": fields.Datetime.now(),
            "ticket_cod_estado": status.cod_estado,
            "ticket_descripcion": status.descripcion_estado,
        }
        if status.is_done:
            vals["state"] = "ready"
            vals["file_url"] = status.archivo_url
            vals["file_name"] = status.archivo_nombre
        elif status.is_error:
            vals["state"] = "error"
            vals["error_message"] = status.descripcion_estado
        self.write(vals)

    def action_download(self):
        """Descarga el archivo en file_url. Pasa a 'downloaded'."""
        for rec in self:
            rec._download_one()
        return True

    def _download_one(self):
        self.ensure_one()
        if not self.file_url:
            return
        import base64

        client = self.company_id._get_l10n_pe_sire_rest_client()
        content = client.download_file(self.file_url)
        self.write(
            {
                "file_data": base64.b64encode(content),
                "downloaded_at": fields.Datetime.now(),
                "state": "downloaded",
            }
        )
