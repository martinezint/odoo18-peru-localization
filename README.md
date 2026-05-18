# Odoo 18 CE — Localización Perú (Community)

> Localización peruana **completa y de código abierto** para Odoo 18 Community Edition.
> Facturación electrónica SUNAT (UBL 2.1 + XAdES-BES), GRE 2.0, SIRE, PLE, POS, PCGE 2019, retenciones, percepciones, detracciones.

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
![Odoo](https://img.shields.io/badge/Odoo-18.0%20CE-purple)
![Status](https://img.shields.io/badge/status-WIP-orange)

## ¿Por qué existe?

Odoo Enterprise trae `l10n_pe_edi` pero **no es Open Source y cuesta dinero**.
Las charlas de OCA/l10n-peru llevan años estancadas: las ramas 17.0 y 18.0 están vacías.
Este proyecto cierra ese gap con módulos AGPL-3 production-ready, mantenidos en abierto.

## Estado por módulo

| # | Módulo | Estado | Fase |
|---|---|---|---|
|  1 | `l10n_pe_base_extras`             | 🟡 WIP | 1 |
|  2 | `l10n_pe_coa_pcge2019`            | ⚪ TODO | 1 |
|  3 | `l10n_pe_taxes_extras`            | ⚪ TODO | 1 |
|  4 | `l10n_pe_detracciones`            | ⚪ TODO | 2 |
|  5 | `l10n_pe_exchange_rate_sbs`       | ⚪ TODO | 2 |
|  6 | `l10n_pe_partner_inbox`           | ⚪ TODO | 2 |
|  7 | `l10n_pe_edi`                     | ⚪ TODO | 2 |
|  8 | `l10n_pe_edi_transport_sunat_soap`| ⚪ TODO | 2 |
|  9 | `l10n_pe_edi_gre`                 | ⚪ TODO | 3 |
| 10 | `l10n_pe_edi_retention`           | ⚪ TODO | 3 |
| 11 | `l10n_pe_sire`                    | ⚪ TODO | 3 |
| 12 | `l10n_pe_ple`                     | ⚪ TODO | 3 |
| 13 | `l10n_pe_pos_edi`                 | ⚪ TODO | 4 |
| 14 | `l10n_pe_reports_pdf`             | ⚪ TODO | 4 |

## Quick start

```bash
# 1. Clonar dependencias OCA
make deps

# 2. Configurar entorno
cp .env.example .env
$EDITOR .env       # ajustar POSTGRES_PASSWORD

# 3. Levantar stack
make up

# 4. Abrir http://localhost:8169 y crear BD con Country=Peru
```

Más detalle en [docs/installation.md](docs/installation.md).

## Stack

- Odoo 18.0 CE
- PostgreSQL 16
- Python 3.12
- Firma XAdES: `python-xmlsec` (libxmlsec1)
- SOAP SUNAT: `zeep`
- GRE 2.0 REST: `httpx`

## Contribuir

Lee [CONTRIBUTING.md](CONTRIBUTING.md) (TODO) antes de mandar PR.
Instala `pre-commit install` después de clonar.

## Licencia

[AGPL-3.0](LICENSE) — cualquier fork debe publicar sus mejoras.
