#!/usr/bin/env python3
"""Genera un certificado self-signed PFX para desarrollo y tests.

NO usar en producción. SUNAT no acepta esto en BETA (necesita el cert demo de
Llama-PE) ni en producción. Sirve para:
- Tests unitarios de firma XAdES (verificación estructural)
- Smoke test del flujo de carga de cert en res.company

Uso:
    python scripts/generate_dev_cert.py
    # Escribe en certificates/dev_cert.pfx con password '123456'

Idempotente: si el archivo ya existe, no lo regenera.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "certificates" / "dev_cert.pfx"
DEFAULT_PASSWORD = b"123456"


def generate(output: Path, password: bytes) -> None:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "PE"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "l10n-peru-ce DEV"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Development Self-Signed (NOT FOR PRODUCTION)"),
        ]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365 * 5))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256(), default_backend())
    )

    pfx = pkcs12.serialize_key_and_certificates(
        name=b"l10n-peru-ce-dev",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pfx)
    output.chmod(0o600)
    print(f"✓ Wrote dev cert to {output} (password: {password.decode()})")
    print(f"  Subject: {subject.rfc4514_string()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--password", type=str, default=DEFAULT_PASSWORD.decode())
    parser.add_argument("--force", action="store_true", help="Regenerar incluso si ya existe")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        print(f"✓ Cert ya existe en {args.output} (usa --force para regenerar)")
        return 0

    try:
        generate(args.output, args.password.encode())
    except ImportError as exc:
        print(f"ERROR: falta dependencia Python: {exc}", file=sys.stderr)
        print("  → pip install cryptography", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
