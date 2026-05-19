# Odoo 18 CE — Localización Perú (Community)

> Localización peruana **completa y de código abierto** para Odoo 18 Community Edition.
> Facturación electrónica SUNAT (UBL 2.1 + XAdES-BES), GRE 2.0, SIRE, PLE, POS, PCGE 2019, retenciones, percepciones, detracciones.

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
![Odoo](https://img.shields.io/badge/Odoo-18.0%20CE-purple)
![Tests](https://img.shields.io/badge/tests-455%20passing-brightgreen)

## ¿Por qué existe?

Odoo Enterprise trae `l10n_pe_edi` pero **no es Open Source y cuesta dinero**.
Las charlas de OCA/l10n-peru llevan años estancadas: las ramas 17.0 y 18.0
están vacías. Este proyecto cierra ese gap con módulos AGPL-3
production-ready, mantenidos en abierto.

## Estado por módulo

| # | Módulo | Cubre |
|---|---|---|
|  1 | `l10n_pe_base_extras`             | Validación RUC/DNI/CE (mod 11), régimen tributario, consulta apis.net.pe |
|  2 | `l10n_pe_coa_pcge2019`            | PCGE + fp por régimen + post-init chart |
|  3 | `l10n_pe_taxes_extras`            | Retenciones, percepciones, ICBPER, IVAP, ISC |
|  4 | `l10n_pe_detracciones`            | Catálogo SUNAT + cálculo en `account.move` |
|  5 | `l10n_pe_exchange_rate_sbs`       | Cron diario USD/EUR desde SBS |
|  6 | `l10n_pe_partner_inbox`           | Upload XML proveedor → borrador de factura |
|  7 | `l10n_pe_edi`                     | UBL 2.1 + firma XAdES-BES con `python-xmlsec` |
|  8 | `l10n_pe_edi_transport_sunat_soap`| `sendBill` sync + `sendSummary` async + cron polling |
|  9 | `l10n_pe_edi_gre`                 | GRE 2.0 REST + OAuth2 + DespatchAdvice UBL + cron + stock.picking wire-up |
| 10 | `l10n_pe_edi_retention`           | Comprobantes 20 (Retención) y 40 (Percepción) UBL |
| 11 | `l10n_pe_sire`                    | REST + tickets propuesta RVIE / RCE |
| 12 | `l10n_pe_ple`                     | PLE 5.x: Ventas 14.1, Compras 8.1, Diario 5.1 |
| 13 | `l10n_pe_pos_edi`                 | RC + auto-send a SUNAT |
| 14 | `l10n_pe_reports_pdf`             | QR RS 097-2012 + representación impresa |
| 15 | `l10n_pe_double_entry_6_9`        | Doble apunte PCGE clase 6 ↔ clase 9 vía 79 (obligatorio SUNAT) |
| 16 | `l10n_pe_ubigeo`                  | Catálogo UBIGEO INEI (Lima Metropolitana + capitales departamentales) |

## Flujos end-to-end soportados

- **Factura/Boleta electrónica**: postear → "Generar EDI" → "Enviar a SUNAT" (sync) → CDR aceptado.
- **GRE Remitente**: `stock.picking` → "Generar y enviar a SUNAT" (async) → cron polling 15 min.
- **POS RC**: cierre sesión → wizard genera Resumen Diario → opcional auto-send (async) → cron polling 10 min.
- **Retenciones / Percepciones**: crear documento → líneas con facturas origen → UBL firmado.
- **SIRE**: solicitar propuesta → polling ticket → descarga TXT.
- **PLE**: wizard por libro + período → TXT con naming SUNAT.
- **Doble apunte 6↔9**: al postear factura de gasto → genera asiento contrapartida en clase 9 (función) + 79 (puente), automático o batch.

## Quick start

```bash
# 1. Clonar repo + dependencias OCA
git clone https://github.com/martinezint/odoo18-peru-localization.git
cd odoo18-peru-localization
make deps

# 2. Configurar entorno
cp .env.example .env
$EDITOR .env       # ajustar POSTGRES_PASSWORD

# 3. Levantar stack (Odoo 18 + PG 16, build de Dockerfile propio con xmlsec)
make up

# 4. Abrir http://localhost:8169 y crear BD con Country=Peru
```

Más detalle en [docs/installation.md](docs/installation.md).

## Stack técnico

- **Odoo 18.0 CE** (sin Enterprise)
- **PostgreSQL 16**
- **Python 3.12**
- **Firma XAdES-BES**: `xmlsec` (binding libxmlsec1, compilado desde fuente
  para evitar mismatch con lxml — ver [Dockerfile](Dockerfile))
- **SOAP SUNAT**: `zeep`
- **GRE 2.0 REST + SIRE REST**: `httpx`
- **QR**: `qrcode`
- **CI**: GitHub Actions con matrix PG 15/16 + pre-commit lint

## Para contribuir

```bash
pip install -r requirements-dev.txt
pre-commit install
# Después, cada commit pasa por ruff (lint+format) + isort
```

PRs bienvenidos. Lee el commit log para ver el patrón de mensajes.

## Estado de los crons automáticos

| Cron | Frecuencia | Propósito |
|---|---|---|
| Peru: actualizar T/C SBS diario | 1 día | Trae tipo de cambio USD/EUR |
| Peru SUNAT: poll tickets RC async | 10 min | Recoge CDR de RC enviados con `sendSummary` |
| Peru SUNAT: poll tickets GRE 2.0 (REST) | 15 min | Recoge estado de GRE enviadas |

## Limitaciones conocidas (v3 / próximas iteraciones)

- **GRE Transportista (cód 31)**: la infra REST funciona; falta el UBL específico (similar a Remitente).
- **PLE Mayor 6.1** y **Inventarios 3.x**: pendientes (similar pattern).
- **SIRE conciliación**: descarga la propuesta pero no la concilia automáticamente contra `account.move`.
- **Mail alias para `partner_inbox`**: por ahora solo upload manual del XML.
- **`account.payment.register` wizard extension** para retenciones automáticas al pagar.

## Licencia

[AGPL-3.0](LICENSE) — cualquier fork debe publicar sus mejoras.

## Repo

<https://github.com/martinezint/odoo18-peru-localization>
