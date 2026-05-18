# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, fields, models


STATE_SELECTION = [
    ("draft", "Borrador"),
    ("signed", "Firmado"),
    ("sent", "Enviado"),
    ("accepted", "Aceptado por SUNAT"),
    ("rejected", "Rechazado por SUNAT"),
    ("error", "Error"),
]


class L10nPeEdiDocument(models.Model):
    """Documento electrónico SUNAT vinculado a un account.move.

    Mantiene el XML firmado, el estado del flujo y trazabilidad. Es la pieza
    independiente del transport (SOAP, REST GRE, OSE) — cada transport
    extiende este modelo para añadir su propia info de envío y respuesta.
    """
    _name = "l10n.pe.edi.document"
    _description = "Documento EDI SUNAT (Perú)"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(
        string="Nombre archivo SUNAT",
        readonly=True,
        copy=False,
        help="Nombre estándar SUNAT: RUC-TIPO-SERIE-NUMERO.xml "
             "(ej. 20131312955-01-F001-1.xml).",
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Comprobante",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="move_id.company_id",
        store=True,
        index=True,
    )
    state = fields.Selection(
        selection=STATE_SELECTION,
        default="draft",
        required=True,
        index=True,
        # Note: tracking removed — el modelo no hereda mail.thread.
        # Cuando añadamos chatter (siguiente iteración), añadir mail.thread
        # y restaurar tracking=True.
    )
    xml_unsigned = fields.Binary(
        string="XML sin firmar",
        attachment=True,
        readonly=True,
    )
    xml_signed = fields.Binary(
        string="XML firmado",
        attachment=True,
        readonly=True,
    )
    digest_value = fields.Char(
        string="DigestValue (firma)",
        readonly=True,
        help="Hash SHA-256 del XML firmado. Útil para integridad y QR.",
    )
    error_message = fields.Text(string="Mensaje de error", readonly=True)
    last_action_at = fields.Datetime(string="Último cambio", readonly=True)

    _sql_constraints = [
        ("move_unique", "UNIQUE(move_id)",
         "Solo un documento EDI por comprobante."),
    ]

    def _build_sunat_filename(self, move):
        """Construye el nombre SUNAT estándar: RUC-TIPO-SERIE-NUMERO.xml.

        Ejemplo: 20131312955-01-F001-1.xml para una Factura.
        """
        company_ruc = (move.company_id.vat or "").strip()
        doc_type = self._get_sunat_doc_type_code(move)
        # move.name viene como "F001/00000001" — convertimos a "F001-1"
        ref = (move.name or "").replace("/", "-").lstrip("-")
        return f"{company_ruc}-{doc_type}-{ref}.xml"

    @staticmethod
    def _get_sunat_doc_type_code(move) -> str:
        """Mapea move.move_type → código SUNAT catálogo 01.

        v1: solo Factura (01). Otros se añaden en módulos siguientes (Boleta 03,
        NC 07, ND 08).
        """
        if move.move_type == "out_invoice":
            return "01"  # Factura (default — boletas serán otro módulo)
        if move.move_type == "out_refund":
            return "07"  # Nota de Crédito
        return "01"
