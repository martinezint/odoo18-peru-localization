# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Scraper de la página pública de la SBS de tipos de cambio promedio.

La SBS publica diariamente (días hábiles, ~17:00 hora Lima) los tipos de cambio
de monedas extranjeras. Fines de semana y feriados no publica.

URL pública: https://www.sbs.gob.pe/app/pp/sistip_portal/paginas/publicacion/tipocambiopromedio.aspx

Estrategia de scraping:
- GET con parámetro de fecha → HTML con tabla
- lxml para parsear, XPath/CSS sobre la tabla
- Mapeo de nombre de moneda SBS → código ISO 4217

Si SBS cambia el HTML, este módulo se rompe. Mitigación: tests con HTML fixtures
para detectar cambios temprano + posibilidad futura de añadir otro provider
(apis.net.pe expone también este dato).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import requests
from lxml import html as lxml_html

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SBS_BASE_URL = (
    "https://www.sbs.gob.pe/app/pp/sistip_portal/paginas/publicacion/tipocambiopromedio.aspx"
)
DEFAULT_TIMEOUT = 15


# Mapeo no-exhaustivo de nombres SBS → ISO 4217.
# SBS suele listar como "DOLAR DE N.A.", "EURO", etc.
_SBS_NAME_TO_ISO = (
    ("DOLAR DE N.A.", "USD"),
    ("DOLAR", "USD"),
    ("DÓLAR", "USD"),
    ("DOLLAR", "USD"),
    ("EURO", "EUR"),
    ("LIBRA", "GBP"),
    ("YEN", "JPY"),
    ("FRANCO SUIZO", "CHF"),
    ("REAL", "BRL"),
    ("PESO MEXICANO", "MXN"),
    ("PESO ARGENTINO", "ARS"),
    ("PESO COLOMBIANO", "COP"),
    ("PESO CHILENO", "CLP"),
    ("DOLAR CANADIENSE", "CAD"),
    ("DOLAR AUSTRALIANO", "AUD"),
    ("YUAN", "CNY"),
)


class SbsScrapingError(UserError):
    """Error específico del scraping SBS — se propaga al usuario en UI."""


def sbs_name_to_iso(name: str) -> Optional[str]:
    """Mapea un nombre de moneda como aparece en SBS al código ISO 4217.

    Devuelve None si no hay match (e.g. moneda exótica no listada).
    """
    if not name:
        return None
    name_upper = name.upper().strip()
    for sbs_name, iso in _SBS_NAME_TO_ISO:
        if sbs_name in name_upper:
            return iso
    return None


class SbsScraper:
    """Scraper de tipos de cambio SBS.

    Uso::

        scraper = SbsScraper()
        rates = scraper.fetch(date(2026, 5, 15))
        # rates = {"USD": {"compra": 3.745, "venta": 3.752}, "EUR": {...}}
    """

    def __init__(self, *, base_url: str = SBS_BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    def fetch(self, when: Optional[date] = None) -> dict[str, dict]:
        """Devuelve dict moneda → {compra, venta}.

        Args:
            when: fecha de consulta. None = hoy.

        Vacío si SBS no publica esa fecha (fin de semana, feriado).
        """
        when = when or date.today()
        date_str = when.strftime("%d/%m/%Y")
        params = {"fechaConsulta": date_str}
        try:
            resp = requests.get(self.base_url, params=params, timeout=self.timeout)
            resp.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise SbsScrapingError(_("Timeout consultando SBS (>%d s).") % self.timeout) from exc
        except requests.exceptions.RequestException as exc:
            _logger.exception("SBS request failed")
            raise SbsScrapingError(_("Error consultando SBS: %s") % exc) from exc
        return self.parse(resp.text, when)

    def parse(self, html_text: str, when: date) -> dict[str, dict]:
        """Extrae las filas de la tabla SBS desde HTML.

        SBS estructura: <table class="apemype"> con filas
        <tr><td>Moneda</td><td>Compra</td><td>Venta</td></tr>.
        Si el HTML no contiene la tabla, devuelve dict vacío y loggea warning.
        """
        try:
            tree = lxml_html.fromstring(html_text)
        except Exception as exc:
            raise SbsScrapingError(_("HTML SBS no parseable: %s") % exc) from exc

        # Estructuras posibles que hemos visto en versiones distintas del portal:
        # 1) <table class="apemype">
        # 2) <table id="ctl00_cphContent_grdRecords">
        # 3) <table> dentro de <div id="ContenidoTablaTipoCambio">
        candidate_xpaths = (
            '//table[contains(@class,"apemype")]//tr[td]',
            '//table[contains(@id,"grdRecords")]//tr[td]',
            '//div[contains(@id,"ContenidoTabla")]//table//tr[td]',
            '//table[.//th[contains(translate(text(),"abcdefghijklmnopqrstuvwxyz","ABCDEFGHIJKLMNOPQRSTUVWXYZ"),"MONEDA")]]//tr[td]',
        )

        rows = []
        for xp in candidate_xpaths:
            rows = tree.xpath(xp)
            if rows:
                break

        if not rows:
            _logger.warning(
                "SBS parse: no se encontró tabla de tipos de cambio para %s. "
                "El HTML pudo haber cambiado de estructura.",
                when,
            )
            return {}

        result: dict[str, dict] = {}
        for row in rows:
            cells = [c.text_content().strip() for c in row.xpath("td")]
            if len(cells) < 3:
                continue
            currency_name = cells[0]
            compra_str = cells[1]
            venta_str = cells[2]
            try:
                compra = float(compra_str.replace(",", "."))
                venta = float(venta_str.replace(",", "."))
            except (ValueError, AttributeError):
                continue
            iso = sbs_name_to_iso(currency_name)
            if iso:
                result[iso] = {"compra": compra, "venta": venta, "fecha": when}
        return result
