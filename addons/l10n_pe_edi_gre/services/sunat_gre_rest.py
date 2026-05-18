# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Cliente REST + OAuth2 a SUNAT GRE 2.0.

GRE 2.0 (Guía de Remisión Electrónica) NO usa SOAP como las facturas. Usa:
- OAuth2 client_credentials para obtener un access_token (vigencia ~1h)
- REST POST/GET con Authorization: Bearer <token>

Endpoints (BETA / PRODUCCIÓN):
- Auth (token):     https://api-seguridad.sunat.gob.pe/v1/clientessol/<CLIENT_ID>/oauth2/token/
- Send (BETA):      https://api-cpe-beta.sunat.gob.pe/v1/contribuyente/gem/comprobantes/<numDoc>
- Send (PROD):      https://api-cpe.sunat.gob.pe/v1/contribuyente/gem/comprobantes/<numDoc>
- Status (BETA):    https://api-cpe-beta.sunat.gob.pe/v1/contribuyente/gem/comprobantes/envios/<numTicket>
- Status (PROD):    https://api-cpe.sunat.gob.pe/v1/contribuyente/gem/comprobantes/envios/<numTicket>

Flujo:
1. POST a /oauth2/token/ con grant_type=client_credentials + scope + client_id + secret
2. Recibe access_token + expires_in
3. POST a /comprobantes/<numDoc> con body JSON:
     { archivo: { nomArchivo, arcGreZip (base64 ZIP), hashZip (sha256 hex) } }
   → response: { numTicket }
4. GET a /comprobantes/envios/<numTicket> hasta que indEstado != "01"
   indEstado: 01 EN PROCESO, 03 RECHAZADO, 05 ACEPTADO, 11 ANULADO

Doc oficial SUNAT: https://www.gob.pe/institucion/sunat/normas-legales/
"""
from __future__ import annotations

import hashlib
import logging
from base64 import b64encode
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

_logger = logging.getLogger(__name__)


# ─── Endpoints SUNAT por ambiente ─────────────────────────────────────
ENDPOINTS = {
    "beta": {
        "auth": "https://api-seguridad.sunat.gob.pe/v1/clientessol/{client_id}/oauth2/token/",
        "send": "https://api-cpe-beta.sunat.gob.pe/v1/contribuyente/gem/comprobantes/{num_doc}",
        "status": "https://api-cpe-beta.sunat.gob.pe/v1/contribuyente/gem/comprobantes/envios/{num_ticket}",
        "scope": "https://api-cpe.sunat.gob.pe",
    },
    "production": {
        "auth": "https://api-seguridad.sunat.gob.pe/v1/clientessol/{client_id}/oauth2/token/",
        "send": "https://api-cpe.sunat.gob.pe/v1/contribuyente/gem/comprobantes/{num_doc}",
        "status": "https://api-cpe.sunat.gob.pe/v1/contribuyente/gem/comprobantes/envios/{num_ticket}",
        "scope": "https://api-cpe.sunat.gob.pe",
    },
}

# Códigos SUNAT indEstado para GRE
ESTADO_EN_PROCESO = "01"
ESTADO_RECHAZADO = "03"
ESTADO_ACEPTADO = "05"
ESTADO_ANULADO = "11"

DEFAULT_TIMEOUT = 30


# ─── Excepciones ──────────────────────────────────────────────────────

class GreRestError(Exception):
    """Error genérico del cliente GRE REST."""

    def __init__(self, message: str, *, status_code: int | None = None,
                 sunat_code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.sunat_code = sunat_code


class GreAuthError(GreRestError):
    """Falla específica de OAuth2 (credenciales, scope, etc.)."""


# ─── Token cache ──────────────────────────────────────────────────────

@dataclass
class TokenCache:
    """Cache simple en memoria de un access_token con expiry.

    Útil cuando se hacen varias llamadas en sucesión (no toca DB). Para cache
    persistente, ver `res.company.l10n_pe_gre_token_*` fields.
    """
    token: str = ""
    expires_at: Optional[datetime] = None

    def is_valid(self, safety_window_sec: int = 30) -> bool:
        if not self.token or not self.expires_at:
            return False
        now = datetime.now(timezone.utc)
        return now + timedelta(seconds=safety_window_sec) < self.expires_at


# ─── Status parseado ──────────────────────────────────────────────────

@dataclass
class GreStatus:
    """Resultado de GET /envios/<ticket>."""
    cod_respuesta: str = ""
    ind_estado: str = ""
    error: dict = field(default_factory=dict)
    cdr_base64: str = ""

    @property
    def is_in_process(self) -> bool:
        return self.ind_estado == ESTADO_EN_PROCESO

    @property
    def is_accepted(self) -> bool:
        return self.ind_estado == ESTADO_ACEPTADO

    @property
    def is_rejected(self) -> bool:
        return self.ind_estado == ESTADO_RECHAZADO

    @property
    def is_cancelled(self) -> bool:
        return self.ind_estado == ESTADO_ANULADO


# ─── Cliente principal ────────────────────────────────────────────────

class SunatGreRestClient:
    """Cliente REST para SUNAT GRE 2.0.

    Uso::

        client = SunatGreRestClient(
            client_id="abc...",
            client_secret="xyz...",
            ruc="20131312955",
            environment="beta",
        )
        ticket = client.send_gre("09-T001-1", "20131312955-09-T001-1.zip", zip_bytes)
        status = client.get_status(ticket)
        if status.is_accepted:
            cdr_zip = base64.b64decode(status.cdr_base64)
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        ruc: str,
        environment: str = "beta",
        timeout: int = DEFAULT_TIMEOUT,
        token_cache: Optional[TokenCache] = None,
    ):
        if environment not in ENDPOINTS:
            raise ValueError(f"environment debe ser 'beta' o 'production', no {environment!r}")
        if not client_id or not client_secret:
            raise GreAuthError("client_id y client_secret son obligatorios")
        self.client_id = client_id
        self.client_secret = client_secret
        self.ruc = ruc
        self.environment = environment
        self.timeout = timeout
        self.endpoints = ENDPOINTS[environment]
        self._token_cache = token_cache or TokenCache()

    # ─── OAuth2 ──────────────────────────────────────────────────

    def get_access_token(self, force_refresh: bool = False) -> str:
        """Devuelve un access_token válido. Refresca si caducó o force_refresh=True."""
        if not force_refresh and self._token_cache.is_valid():
            return self._token_cache.token

        url = self.endpoints["auth"].format(client_id=self.client_id)
        body = {
            "grant_type": "client_credentials",
            "scope": self.endpoints["scope"],
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            resp = httpx.post(
                url,
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise GreAuthError(f"Error de red al pedir token: {exc}") from exc

        if resp.status_code != 200:
            raise GreAuthError(
                f"Token denegado: HTTP {resp.status_code} {resp.text[:200]}",
                status_code=resp.status_code,
            )

        data = resp.json()
        access_token = data.get("access_token", "")
        expires_in = int(data.get("expires_in", 3600))
        if not access_token:
            raise GreAuthError("Respuesta SUNAT no contiene access_token")

        self._token_cache.token = access_token
        self._token_cache.expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        )
        _logger.info(
            "GRE: token obtenido, expira en %s s.", expires_in
        )
        return access_token

    # ─── Submission ──────────────────────────────────────────────

    def send_gre(
        self,
        num_doc: str,
        zip_filename: str,
        zip_bytes: bytes,
    ) -> str:
        """POST /comprobantes/<numDoc>. Devuelve numTicket.

        num_doc: identificador para la URL, formato '<tipo>-<serie>-<numero>'.
                 Ejemplo: '09-T001-1' (Remitente, serie T001, num 1).
        zip_filename: nombre lógico del ZIP (no se usa en URL).
        zip_bytes: bytes del ZIP que contiene el XML firmado.
        """
        token = self.get_access_token()
        url = self.endpoints["send"].format(num_doc=num_doc)
        hash_hex = hashlib.sha256(zip_bytes).hexdigest()
        payload = {
            "archivo": {
                "nomArchivo": zip_filename,
                "arcGreZip": b64encode(zip_bytes).decode("ascii"),
                "hashZip": hash_hex,
            },
        }
        try:
            resp = httpx.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise GreRestError(f"Error de red enviando GRE: {exc}") from exc

        if resp.status_code == 401:
            # Token vencido: refresca y reintenta una vez
            _logger.info("GRE: 401, refrescando token y reintentando.")
            self.get_access_token(force_refresh=True)
            return self.send_gre(num_doc, zip_filename, zip_bytes)

        if resp.status_code not in (200, 201, 202):
            try:
                err = resp.json()
                code = err.get("cod") or err.get("codRespuesta") or ""
                msg = err.get("msg") or err.get("descripcion") or resp.text[:300]
            except Exception:
                code = ""
                msg = resp.text[:300]
            raise GreRestError(
                f"SUNAT GRE rechazó el envío: HTTP {resp.status_code} [{code}] {msg}",
                status_code=resp.status_code,
                sunat_code=code,
            )

        data = resp.json()
        ticket = data.get("numTicket", "")
        if not ticket:
            raise GreRestError(f"Respuesta GRE sin numTicket: {data}")
        _logger.info("GRE: ticket %s para num_doc %s.", ticket, num_doc)
        return ticket

    # ─── Status polling ──────────────────────────────────────────

    def get_status(self, num_ticket: str) -> GreStatus:
        """GET /envios/<numTicket>. Devuelve GreStatus."""
        token = self.get_access_token()
        url = self.endpoints["status"].format(num_ticket=num_ticket)
        try:
            resp = httpx.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise GreRestError(f"Error de red consultando status: {exc}") from exc

        if resp.status_code == 401:
            self.get_access_token(force_refresh=True)
            return self.get_status(num_ticket)

        if resp.status_code != 200:
            raise GreRestError(
                f"SUNAT GRE status HTTP {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )

        data = resp.json()
        return GreStatus(
            cod_respuesta=str(data.get("codRespuesta", "")),
            ind_estado=str(data.get("indEstado", "")),
            error=data.get("error") or {},
            cdr_base64=data.get("arcCdr", "") or "",
        )
