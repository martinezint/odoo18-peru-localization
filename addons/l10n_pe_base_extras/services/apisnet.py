# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Cliente HTTP para apis.net.pe (consulta RUC vs SUNAT y DNI vs RENIEC).

apis.net.pe es un proxy público a los padrones SUNAT/RENIEC. Requiere token
desde 2024 (https://apis.net.pe/api-token, free tier ~100 req/día).

El cliente es deliberadamente delgado: solo conoce HTTP. La normalización al
modelo de Odoo (matching de ubigeo, escritura de campos) vive en res.partner.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.apis.net.pe/v1"
DEFAULT_TIMEOUT = 10  # segundos


class ApisNetError(UserError):
    """Error específico de la integración con apis.net.pe."""


class ApisNetClient:
    """Cliente síncrono para apis.net.pe.

    Uso::

        client = ApisNetClient(token="...")
        data = client.consult_ruc("20131312955")
        if data:
            print(data["razonSocial"])
    """

    def __init__(self, token: str, *, base_url: str = API_BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        if not token:
            raise ApisNetError(
                _("Falta el token de apis.net.pe. "
                  "Configúralo en Ajustes → Empresas → tu empresa.")
            )
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, endpoint: str, params: dict[str, str]) -> dict[str, Any] | None:
        """GET genérico. Devuelve dict del JSON, o None si 404. Lanza UserError en otros errores."""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise ApisNetError(_("Timeout consultando apis.net.pe (>%d s).") % self.timeout) from exc
        except requests.exceptions.RequestException as exc:
            _logger.exception("apis.net.pe request failed")
            raise ApisNetError(_("Error de conexión con apis.net.pe: %s") % exc) from exc

        if resp.status_code == 401:
            raise ApisNetError(_("Token apis.net.pe inválido o expirado."))
        if resp.status_code == 422:
            raise ApisNetError(_("Formato del número de documento inválido."))
        if resp.status_code == 429:
            raise ApisNetError(_("Cuota de consultas excedida en apis.net.pe."))
        if resp.status_code == 404:
            return None

        try:
            resp.raise_for_status()
            return resp.json()
        except ValueError as exc:
            raise ApisNetError(_("Respuesta no-JSON de apis.net.pe.")) from exc

    def consult_ruc(self, ruc: str) -> dict[str, Any] | None:
        """Consulta padrón SUNAT por RUC. Devuelve dict o None si no se encuentra."""
        return self._get("ruc", {"numero": ruc})

    def consult_dni(self, dni: str) -> dict[str, Any] | None:
        """Consulta padrón RENIEC por DNI. Devuelve dict o None si no se encuentra."""
        return self._get("dni", {"numero": dni})
