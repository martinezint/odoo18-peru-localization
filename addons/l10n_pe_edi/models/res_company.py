# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_pe_edi_cert_pfx = fields.Binary(
        string="Certificado SUNAT (.pfx)",
        attachment=True,
        groups="base.group_system",
        help="Certificado digital en formato PKCS#12 (.pfx/.p12) emitido por "
             "una entidad acreditada (Llama.PE, Camerfirma, ESign, etc.) "
             "o el demo de SUNAT para BETA. NUNCA exponer en API.",
    )
    l10n_pe_edi_cert_filename = fields.Char(
        string="Nombre archivo cert",
        groups="base.group_system",
    )
    l10n_pe_edi_cert_password = fields.Char(
        string="Password del .pfx",
        groups="base.group_system",
        help="Password con que se exportó el .pfx. Se guarda en BD — protégelo "
             "con permisos estrictos a nivel del servidor.",
    )
    l10n_pe_edi_environment = fields.Selection(
        selection=[
            ("beta", "BETA (pruebas SUNAT)"),
            ("production", "Producción"),
        ],
        string="Ambiente EDI",
        default="beta",
        help="BETA: usa endpoints de prueba de SUNAT; permite usar cert demo "
             "Llama-PE. PRODUCCIÓN: requiere cert real y emite documentos legales.",
    )

    def _get_l10n_pe_edi_signer(self):
        """Construye un XadesBesSigner desde el cert configurado en la empresa.

        Raises UserError si falta cert o password.
        """
        self.ensure_one()
        if not self.l10n_pe_edi_cert_pfx:
            raise UserError(_(
                "No hay certificado SUNAT configurado en la empresa %s. "
                "Súbelo en Ajustes → Empresa → Certificado SUNAT."
            ) % self.name)
        if not self.l10n_pe_edi_cert_password:
            raise UserError(_("Falta el password del certificado .pfx."))

        # Import diferido para no obligar a tener xmlsec si solo se lee el field.
        import base64
        from ..services.xades_signer import XadesBesSigner

        pfx_bytes = base64.b64decode(self.l10n_pe_edi_cert_pfx)
        return XadesBesSigner.from_pfx_bytes(
            pfx_bytes,
            self.l10n_pe_edi_cert_password.encode("utf-8"),
        )
