#!/usr/bin/env python3
"""Carga datos demo de una empresa peruana de prueba.

Crea: 1 empresa con RUC válido de prueba, clientes, productos, y emite
1 factura, 1 boleta y 1 nota de crédito al ambiente BETA de SUNAT.

Uso (dentro del container o con env apuntando a Odoo):
    python scripts/load_demo.py --url http://localhost:8169 --db peru_dev \\
        --user admin --password admin

TODO: implementar tras Fase 2 (necesita l10n_pe_edi listo).
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8169")
    parser.add_argument("--db", default="peru_dev")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    print(f"TODO: cargar demo en {args.url} (db={args.db})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
