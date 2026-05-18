# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Cliente SOAP a SUNAT Facturación Electrónica.

Endpoints:
- BETA:       https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService
- PRODUCCIÓN: https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService

Autenticación HTTP Basic:
- username = <RUC_EMISOR><USUARIO_SOL>  (concatenados, sin separador)
- password = SOL password

Para BETA SUNAT publica credenciales demo:
- RUC: 20131312955 (la propia SUNAT)
- SOL_USER: MODDATOS
- SOL_PASS: MODDATOS

Operaciones:
- sendBill(fileName, contentFile) → sync, devuelve CDR en applicationResponse.
  Usado para Factura, Boleta, NC, ND.
- sendSummary(fileName, contentFile) → async, devuelve ticket; luego se
  consulta con getStatus(ticket). Usado para RC (resúmenes) y RA (bajas).
"""
from __future__ import annotations

import io
import logging
import zipfile

from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client
from zeep.exceptions import Fault, TransportError
from zeep.transports import Transport

_logger = logging.getLogger(__name__)


ENDPOINTS = {
    "beta": "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService",
    "production": "https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService",
}

DEFAULT_TIMEOUT = 60  # segundos — SUNAT puede tardar 30-45s en BETA


class SunatSoapError(Exception):
    """Error de SUNAT con fault_code legible."""

    def __init__(self, fault_code: str, message: str):
        super().__init__(f"SUNAT [{fault_code}] {message}")
        self.fault_code = fault_code
        self.fault_message = message


class SunatBillService:
    """Cliente sendBill SOAP a SUNAT.

    Uso::

        client = SunatBillService(
            ruc="20131312955",
            sol_user="MODDATOS",
            sol_password="MODDATOS",
            environment="beta",
        )
        zip_bytes = client.zip_xml("20131312955-01-F001-1.xml", signed_xml_bytes)
        cdr_bytes = client.send_bill("20131312955-01-F001-1.zip", zip_bytes)
    """

    def __init__(
        self,
        ruc: str,
        sol_user: str,
        sol_password: str,
        environment: str = "beta",
        timeout: int = DEFAULT_TIMEOUT,
        endpoint_override: str | None = None,
    ):
        if environment not in ENDPOINTS:
            raise ValueError(
                f"environment debe ser 'beta' o 'production', no {environment!r}"
            )
        self.endpoint = endpoint_override or ENDPOINTS[environment]
        self.username = f"{ruc}{sol_user}"
        self.password = sol_password
        self.timeout = timeout
        self._client: Client | None = None  # lazy init para no fetch WSDL en construct

    @property
    def client(self) -> Client:
        """Construye el zeep Client la primera vez que se llama (lazy)."""
        if self._client is None:
            session = Session()
            session.auth = HTTPBasicAuth(self.username, self.password)
            transport = Transport(session=session, timeout=self.timeout)
            wsdl_url = f"{self.endpoint}?wsdl"
            _logger.info("SUNAT: fetching WSDL %s", wsdl_url)
            self._client = Client(wsdl_url, transport=transport)
        return self._client

    # ─── Helpers ZIP ─────────────────────────────────────────────────

    @staticmethod
    def zip_xml(xml_filename: str, xml_bytes: bytes) -> bytes:
        """Empaqueta `xml_bytes` en un ZIP con un solo entry `xml_filename`.

        SUNAT exige que el contenido del ZIP tenga exactamente el mismo nombre
        que el ZIP pero con extensión .xml (ej. archivo.zip contiene archivo.xml).
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(xml_filename, xml_bytes)
        return buf.getvalue()

    @staticmethod
    def extract_cdr_from_zip(zip_bytes: bytes) -> bytes:
        """SUNAT devuelve un ZIP cuyo contenido es R-<nombre_original>.xml.

        Devolvemos los bytes del primer XML que empiece con 'R-', o el primer XML
        si no hay match (defensivo).
        """
        if not zip_bytes:
            raise SunatSoapError("CDR_EMPTY", "Respuesta SUNAT vacía (no hay ZIP)")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            for name in names:
                if name.startswith("R-") and name.endswith(".xml"):
                    return zf.read(name)
            for name in names:
                if name.endswith(".xml"):
                    return zf.read(name)
        raise SunatSoapError(
            "CDR_MISSING",
            "El ZIP de respuesta SUNAT no contiene CDR XML",
        )

    # ─── Operaciones SOAP ────────────────────────────────────────────

    def send_bill(self, zip_filename: str, zip_bytes: bytes) -> bytes:
        """Llama sendBill y devuelve los BYTES del CDR XML (ya extraído del ZIP).

        Lanza SunatSoapError si SUNAT devuelve SOAP fault o falla la red.
        El caller pasa el resultado a `cdr_parser.parse_cdr()` para interpretar.
        """
        try:
            cdr_zip_bytes = self.client.service.sendBill(
                fileName=zip_filename,
                contentFile=zip_bytes,
            )
        except Fault as exc:
            raise SunatSoapError(
                fault_code=str(getattr(exc, "code", "") or "SOAP_FAULT"),
                message=exc.message or str(exc),
            ) from exc
        except TransportError as exc:
            raise SunatSoapError("TRANSPORT", str(exc)) from exc
        return self.extract_cdr_from_zip(cdr_zip_bytes)
