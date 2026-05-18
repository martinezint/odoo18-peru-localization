# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError

from ..services.apisnet import ApisNetClient

# Códigos SUNAT catálogo 06 (tipo doc identidad) — definidos en core l10n_pe
# vía l10n_latam.identification.type.l10n_pe_vat_code
SUNAT_DOC_RUC = "6"
SUNAT_DOC_DNI = "1"
SUNAT_DOC_CE = "4"
SUNAT_DOC_PASSPORT = "7"

CE_MIN_LEN = 9
CE_MAX_LEN = 12
DNI_LEN = 8


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ─── Validaciones ──────────────────────────────────────────────────

    @api.constrains("vat", "l10n_latam_identification_type_id")
    def _l10n_pe_check_identification(self):
        """Valida el número del documento según el tipo SUNAT (catálogo 06).

        - RUC (6): reutiliza ``check_vat_pe`` del módulo core ``base_vat``
          (algoritmo mod 11 oficial SUNAT).
        - DNI (1): 8 dígitos numéricos.
        - CE (4): alfanumérico, 9-12 caracteres.
        - Otros (pasaporte, etc.): sin validación de formato.

        Solo se valida si el tipo de identificación tiene ``l10n_pe_vat_code``
        (campo añadido por core ``l10n_pe`` para mapear al catálogo SUNAT 06).
        """
        for partner in self:
            id_type = partner.l10n_latam_identification_type_id
            if not id_type or not partner.vat:
                continue
            code = id_type.l10n_pe_vat_code
            if not code:
                continue
            vat = partner.vat.strip()
            if code == SUNAT_DOC_RUC:
                # check_vat_pe está en base_vat; aplica mod 11 SUNAT.
                if not partner.check_vat_pe(vat):
                    raise ValidationError(
                        _("RUC «%s» inválido: el dígito verificador no coincide (mod 11 SUNAT).")
                        % vat
                    )
            elif code == SUNAT_DOC_DNI:
                if len(vat) != DNI_LEN or not vat.isdigit():
                    raise ValidationError(
                        _("DNI «%s» inválido: debe tener exactamente %d dígitos numéricos.")
                        % (vat, DNI_LEN)
                    )
            elif code == SUNAT_DOC_CE:
                if not (CE_MIN_LEN <= len(vat) <= CE_MAX_LEN and vat.isalnum()):
                    raise ValidationError(
                        _("CE «%s» inválido: debe ser alfanumérico de %d a %d caracteres.")
                        % (vat, CE_MIN_LEN, CE_MAX_LEN)
                    )

    # ─── Consulta online (apis.net.pe) ─────────────────────────────────

    def action_l10n_pe_query_apisnet(self):
        """Botón de UI: consulta apis.net.pe y autocompleta name/dirección.

        Determina el endpoint (RUC vs DNI) según el tipo de identificación.
        Solo procesa el primer registro (botón en form view).
        """
        self.ensure_one()
        if not self.vat:
            raise UserError(_("Ingresa el número de documento (RUC/DNI) antes de consultar."))
        id_type = self.l10n_latam_identification_type_id
        if not id_type or not id_type.l10n_pe_vat_code:
            raise UserError(_("Asigna primero el «Tipo de documento de identidad»."))

        company = self.env.company
        client = ApisNetClient(company.l10n_pe_apisnet_token)
        code = id_type.l10n_pe_vat_code
        vat = self.vat.strip()

        if code == SUNAT_DOC_RUC:
            data = client.consult_ruc(vat)
            if not data:
                raise UserError(_("RUC %s no encontrado en SUNAT.") % vat)
            self._l10n_pe_fill_from_ruc(data)
        elif code == SUNAT_DOC_DNI:
            data = client.consult_dni(vat)
            if not data:
                raise UserError(_("DNI %s no encontrado en RENIEC.") % vat)
            self._l10n_pe_fill_from_dni(data)
        else:
            raise UserError(
                _("Tipo de documento «%s» no soportado para consulta online.") % id_type.name
            )

    def _l10n_pe_fill_from_ruc(self, data):
        """Aplica la respuesta apis.net.pe sobre el partner (idempotente).

        No sobreescribe ``country_id`` si ya está fijado. No toca campos que el
        usuario haya completado manualmente (por convención: solo escribe vacíos).
        """
        vals = {"is_company": True}
        razon = (data.get("razonSocial") or "").strip()
        if razon and not self.name:
            vals["name"] = razon
        elif razon:
            # Si ya hay name distinto, igual lo actualizamos para reflejar SUNAT.
            vals["name"] = razon
        direccion = (data.get("direccion") or "").strip()
        if direccion:
            vals["street"] = direccion
        if not self.country_id:
            peru = self.env.ref("base.pe", raise_if_not_found=False)
            if peru:
                vals["country_id"] = peru.id
        self.write(vals)

    def _l10n_pe_fill_from_dni(self, data):
        """Construye el nombre desde apellidos + nombres y lo escribe."""
        parts = [
            (data.get("apellidoPaterno") or "").strip(),
            (data.get("apellidoMaterno") or "").strip(),
            (data.get("nombres") or "").strip(),
        ]
        full = " ".join(p for p in parts if p)
        vals = {"is_company": False}
        if full:
            vals["name"] = full
        if not self.country_id:
            peru = self.env.ref("base.pe", raise_if_not_found=False)
            if peru:
                vals["country_id"] = peru.id
        self.write(vals)
