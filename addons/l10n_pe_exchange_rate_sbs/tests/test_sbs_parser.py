# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from datetime import date

from odoo.tests.common import TransactionCase, tagged

from ..services.sbs import SbsScraper, sbs_name_to_iso


# Fixture: HTML simulado de la página SBS con la tabla de tipos de cambio
SBS_SAMPLE_HTML = """
<html>
<head><title>SBS</title></head>
<body>
<form>
<table class="apemype">
  <thead>
    <tr><th>Moneda</th><th>Compra</th><th>Venta</th></tr>
  </thead>
  <tbody>
    <tr><td>DOLAR DE N.A.</td><td>3.745</td><td>3.752</td></tr>
    <tr><td>EURO</td><td>4.120</td><td>4.180</td></tr>
    <tr><td>LIBRA ESTERLINA</td><td>4.800</td><td>4.900</td></tr>
    <tr><td>YEN JAPONES</td><td>0.024</td><td>0.025</td></tr>
  </tbody>
</table>
</form>
</body>
</html>
"""

# HTML sin tabla (e.g. fin de semana)
SBS_EMPTY_HTML = """
<html><body><p>No hay información para esta fecha.</p></body></html>
"""

# HTML con comas como separador decimal (variante europea SBS antigua)
SBS_COMMA_DECIMAL_HTML = """
<html><body>
<table class="apemype">
  <tr><td>DOLAR</td><td>3,745</td><td>3,752</td></tr>
</table>
</body></html>
"""


@tagged("post_install", "-at_install", "l10n_pe_exchange_rate_sbs")
class TestSbsNameToIso(TransactionCase):
    """Unit tests del mapeo nombre SBS → código ISO 4217."""

    def test_dolar_variants(self):
        for name in ("DOLAR DE N.A.", "DOLAR", "DÓLAR", "Dollar US", "dolar"):
            self.assertEqual(sbs_name_to_iso(name), "USD", f"{name!r} → USD")

    def test_euro(self):
        self.assertEqual(sbs_name_to_iso("EURO"), "EUR")
        self.assertEqual(sbs_name_to_iso("euro"), "EUR")

    def test_libra(self):
        self.assertEqual(sbs_name_to_iso("LIBRA ESTERLINA"), "GBP")

    def test_yen(self):
        self.assertEqual(sbs_name_to_iso("YEN JAPONES"), "JPY")

    def test_unknown_returns_none(self):
        self.assertIsNone(sbs_name_to_iso("FOOBAR XYZ"))

    def test_empty_returns_none(self):
        self.assertIsNone(sbs_name_to_iso(""))
        self.assertIsNone(sbs_name_to_iso(None))


@tagged("post_install", "-at_install", "l10n_pe_exchange_rate_sbs")
class TestSbsParser(TransactionCase):
    """Unit tests del parser sobre HTML fixtures (sin tocar red)."""

    def setUp(self):
        super().setUp()
        self.scraper = SbsScraper()
        self.when = date(2026, 5, 15)

    def test_parse_sample_html_finds_all_currencies(self):
        result = self.scraper.parse(SBS_SAMPLE_HTML, self.when)
        self.assertEqual(len(result), 4)
        self.assertIn("USD", result)
        self.assertIn("EUR", result)
        self.assertIn("GBP", result)
        self.assertIn("JPY", result)

    def test_parse_usd_values(self):
        result = self.scraper.parse(SBS_SAMPLE_HTML, self.when)
        self.assertEqual(result["USD"]["compra"], 3.745)
        self.assertEqual(result["USD"]["venta"], 3.752)
        self.assertEqual(result["USD"]["fecha"], self.when)

    def test_parse_eur_values(self):
        result = self.scraper.parse(SBS_SAMPLE_HTML, self.when)
        self.assertEqual(result["EUR"]["compra"], 4.120)
        self.assertEqual(result["EUR"]["venta"], 4.180)

    def test_parse_empty_html_returns_empty_dict(self):
        result = self.scraper.parse(SBS_EMPTY_HTML, self.when)
        self.assertEqual(result, {})

    def test_parse_comma_decimal(self):
        result = self.scraper.parse(SBS_COMMA_DECIMAL_HTML, self.when)
        self.assertIn("USD", result)
        self.assertEqual(result["USD"]["compra"], 3.745)
        self.assertEqual(result["USD"]["venta"], 3.752)
