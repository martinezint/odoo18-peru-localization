# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Cliente REST + OAuth2 a SUNAT SIRE.

SIRE (Sistema Integrado de Registros Electrónicos) reemplaza progresivamente
a PLE desde 2024. Tiene dos libros principales:
- RVIE: Registro de Ventas e Ingresos Electrónico
- RCE:  Registro de Compras Electrónico

Modelo asíncrono basado en TICKETS:
1. POST /comprobantes/exportapropuesta/... → devuelve numTicket
2. GET  /exportapropuesta/.../<numTicket> → polling hasta status TERMINADO
3. Download del archivo final (URL en la respuesta)

Endpoints:
- Auth:        https://api-seguridad.sunat.gob.pe/v1/clientessol/<client_id>/oauth2/token/
               (mismo endpoint que GRE, scope distinto)
- BETA:        https://api-sire-beta.sunat.gob.pe/v1/contribuyente/migeigv/libros/...
- PROD:        https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/...

NOTA: SUNAT actualiza las rutas SIRE con frecuencia. Las constantes ENDPOINTS
de abajo reflejan los paths a fecha del commit; revisar manual del programador
SUNAT vigente antes de un release.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx

_logger = logging.getLogger(__name__)


# ─── Endpoints SIRE por ambiente ──────────────────────────────────────
SIRE_BASE = {
    "beta": "https://api-sire-beta.sunat.gob.pe",
    "production": "https://api-sire.sunat.gob.pe",
}

AUTH_URL_TPL = "https://api-seguridad.sunat.gob.pe/v1/clientessol/{client_id}/oauth2/token/"
SCOPE_SIRE = "https://api-sire.sunat.gob.pe"

# Paths (relativos a SIRE_BASE)
PATH_RCE_PROPUESTA_POST = "/v1/contribuyente/migeigv/libros/rce/propuesta/web/propuesta/{periodo}/exportacioncomprobantepropuesta"
PATH_RVIE_PROPUESTA_POST = (
    "/v1/contribuyente/migeigv/libros/rvie/propuesta/web/propuesta/{periodo}/exportarpropuesta"
)
PATH_TICKET_STATUS = (
    "/v1/contribuyente/migeigv/libros/{libro}/propuesta/web/consultaticket/{ticket}"
)

DEFAULT_TIMEOUT = 60

# Estados SUNAT SIRE comunes (campo 'estado' o 'codEstado' según endpoint)
ESTADO_EN_PROCESO = "01"
ESTADO_TERMINADO = "02"
ESTADO_ERROR = "03"


# ─── Excepciones ──────────────────────────────────────────────────────


class SireError(Exception):
    """Error genérico SIRE."""

    def __init__(
        self, message: str, *, status_code: int | None = None, sunat_code: str | None = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.sunat_code = sunat_code


class SireAuthError(SireError):
    """Falla específica del flow OAuth2."""


# ─── Cache de token ───────────────────────────────────────────────────


@dataclass
class SireTokenCache:
    """Mismo patrón que GRE TokenCache pero independiente (scope distinto)."""

    token: str = ""
    expires_at: datetime | None = None

    def is_valid(self, safety_window_sec: int = 30) -> bool:
        if not self.token or not self.expires_at:
            return False
        return datetime.now(UTC) + timedelta(seconds=safety_window_sec) < self.expires_at


# ─── Status response ──────────────────────────────────────────────────


@dataclass
class SireTicketStatus:
    """Resultado de polling de ticket SIRE."""

    cod_estado: str = ""
    descripcion_estado: str = ""
    archivo_url: str = ""  # URL para descarga cuando TERMINADO
    archivo_nombre: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def is_in_process(self) -> bool:
        return self.cod_estado == ESTADO_EN_PROCESO

    @property
    def is_done(self) -> bool:
        return self.cod_estado == ESTADO_TERMINADO

    @property
    def is_error(self) -> bool:
        return self.cod_estado == ESTADO_ERROR


# ─── Cliente principal ────────────────────────────────────────────────


class SunatSireRestClient:
    """Cliente REST SIRE.

    Uso::

        client = SunatSireRestClient(
            client_id="...", client_secret="...",
            ruc="20131312955", environment="beta",
        )
        ticket = client.request_rce_propuesta("202604")
        # poll cada N segundos
        status = client.get_ticket_status(ticket, libro="rce")
        if status.is_done:
            file_bytes = client.download_file(status.archivo_url)
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        ruc: str,
        environment: str = "beta",
        timeout: int = DEFAULT_TIMEOUT,
        token_cache: SireTokenCache | None = None,
    ):
        if environment not in SIRE_BASE:
            raise ValueError(f"environment debe ser 'beta' o 'production', no {environment!r}")
        if not client_id or not client_secret:
            raise SireAuthError("client_id y client_secret son obligatorios")
        self.client_id = client_id
        self.client_secret = client_secret
        self.ruc = ruc
        self.environment = environment
        self.timeout = timeout
        self.base = SIRE_BASE[environment]
        self._token_cache = token_cache or SireTokenCache()

    # ─── OAuth2 ──────────────────────────────────────────────────

    def get_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._token_cache.is_valid():
            return self._token_cache.token

        url = AUTH_URL_TPL.format(client_id=self.client_id)
        body = {
            "grant_type": "client_credentials",
            "scope": SCOPE_SIRE,
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
            raise SireAuthError(f"Error de red al pedir token SIRE: {exc}") from exc

        if resp.status_code != 200:
            raise SireAuthError(
                f"Token SIRE denegado: HTTP {resp.status_code} {resp.text[:200]}",
                status_code=resp.status_code,
            )

        data = resp.json()
        access_token = data.get("access_token", "")
        expires_in = int(data.get("expires_in", 3600))
        if not access_token:
            raise SireAuthError("Respuesta SUNAT sin access_token")
        self._token_cache.token = access_token
        self._token_cache.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        _logger.info("SIRE token obtenido, expira en %s s.", expires_in)
        return access_token

    # ─── Helpers ─────────────────────────────────────────────────

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Hace request con auth + retry 1 vez en 401 (token refresh)."""
        token = self.get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        try:
            resp = httpx.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        except httpx.HTTPError as exc:
            raise SireError(f"Error de red SIRE {method} {url}: {exc}") from exc
        if resp.status_code == 401:
            _logger.info("SIRE: 401, refrescando token y reintentando.")
            self.get_access_token(force_refresh=True)
            token = self._token_cache.token
            headers["Authorization"] = f"Bearer {token}"
            try:
                resp = httpx.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
            except httpx.HTTPError as exc:
                raise SireError(f"Retry tras 401 falló: {exc}") from exc
        return resp

    # ─── Propuestas ──────────────────────────────────────────────

    def request_rce_propuesta(self, periodo: str) -> str:
        """POST RCE propuesta. periodo = 'YYYYMM' (e.g. '202604'). Devuelve ticket."""
        self._validate_periodo(periodo)
        url = self.base + PATH_RCE_PROPUESTA_POST.format(periodo=periodo)
        return self._post_propuesta(url, libro="rce", periodo=periodo)

    def request_rvie_propuesta(self, periodo: str) -> str:
        self._validate_periodo(periodo)
        url = self.base + PATH_RVIE_PROPUESTA_POST.format(periodo=periodo)
        return self._post_propuesta(url, libro="rvie", periodo=periodo)

    def _post_propuesta(self, url: str, *, libro: str, periodo: str) -> str:
        resp = self._request("POST", url)
        if resp.status_code not in (200, 201, 202):
            self._raise_error(resp, f"SIRE POST {libro} propuesta {periodo}")
        try:
            data = resp.json()
        except ValueError:
            raise SireError(f"Respuesta SIRE no es JSON: {resp.text[:300]}")
        ticket = data.get("numTicket") or data.get("ticket") or ""
        if not ticket:
            raise SireError(f"Respuesta SIRE sin numTicket: {data}")
        _logger.info("SIRE %s propuesta %s → ticket %s", libro, periodo, ticket)
        return ticket

    # ─── Status polling ──────────────────────────────────────────

    def get_ticket_status(self, ticket: str, *, libro: str) -> SireTicketStatus:
        """GET status de un ticket. libro debe ser 'rce' o 'rvie'."""
        if libro not in ("rce", "rvie"):
            raise ValueError(f"libro debe ser 'rce' o 'rvie', no {libro!r}")
        url = self.base + PATH_TICKET_STATUS.format(libro=libro, ticket=ticket)
        resp = self._request("GET", url)
        if resp.status_code != 200:
            self._raise_error(resp, f"SIRE GET ticket {ticket}")
        try:
            data = resp.json()
        except ValueError:
            raise SireError(f"Status SIRE no JSON: {resp.text[:300]}")

        return SireTicketStatus(
            cod_estado=str(data.get("codEstado") or data.get("estado") or ""),
            descripcion_estado=str(data.get("desEstado") or data.get("descripcion") or ""),
            archivo_url=data.get("archivo", {}).get("url", "")
            if isinstance(data.get("archivo"), dict)
            else "",
            archivo_nombre=data.get("archivo", {}).get("nombre", "")
            if isinstance(data.get("archivo"), dict)
            else "",
            raw=data,
        )

    # ─── File download ───────────────────────────────────────────

    def download_file(self, url: str) -> bytes:
        """Descarga un archivo desde la URL devuelta en el status del ticket."""
        resp = self._request("GET", url)
        if resp.status_code != 200:
            self._raise_error(resp, f"SIRE download {url}")
        return resp.content

    # ─── Internos ────────────────────────────────────────────────

    @staticmethod
    def _validate_periodo(periodo: str):
        """periodo debe ser 'YYYYMM' formato SUNAT."""
        if not periodo or len(periodo) != 6 or not periodo.isdigit():
            raise ValueError(f"periodo debe ser YYYYMM (6 dígitos), recibido: {periodo!r}")
        year = int(periodo[:4])
        month = int(periodo[4:])
        if year < 2018 or year > 2100:
            raise ValueError(f"año fuera de rango razonable: {year}")
        if month < 1 or month > 12:
            raise ValueError(f"mes inválido: {month}")

    @staticmethod
    def _raise_error(resp: httpx.Response, context: str):
        """Construye SireError con detalles desde la response."""
        try:
            data = resp.json()
            code = data.get("cod") or data.get("codRespuesta") or ""
            msg = data.get("msg") or data.get("descripcion") or resp.text[:200]
        except Exception:
            code = ""
            msg = resp.text[:200]
        raise SireError(
            f"{context}: HTTP {resp.status_code} [{code}] {msg}",
            status_code=resp.status_code,
            sunat_code=code,
        )
