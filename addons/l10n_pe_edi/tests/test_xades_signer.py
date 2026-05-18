# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Tests del XAdES-BES signer.

Genera un certificado self-signed en memoria para cada test (no toca el cert
de la empresa). Verifica que firma y luego verifica correctamente.
"""

from datetime import datetime, timedelta, timezone

from odoo.tests.common import TransactionCase, tagged

from ..services.ubl_builder import NS_DS
from ..services.xades_signer import XadesBesSigner, XadesSigningError


def _make_self_signed_pem():
    """Genera (cert_pem, key_pem) self-signed RSA-2048."""
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Test PE EDI"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=30))
        .sign(key, hashes.SHA256(), default_backend())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def _make_self_signed_pfx(password: bytes = b"123456") -> bytes:
    """Genera un PFX self-signed (para tests de from_pfx)."""
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Test PFX"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=30))
        .sign(key, hashes.SHA256(), default_backend())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )


def _make_test_root_with_placeholder():
    """Construye un UBL Invoice mínimo con placeholder de firma."""
    from datetime import date, time
    from decimal import Decimal

    from ..services.ubl_builder import (
        Invoice, InvoiceLine, Party, UblInvoiceBuilder,
    )
    inv = Invoice(
        serie_number="F001-1",
        issue_date=date(2026, 5, 15),
        issue_time=time(10, 30, 0),
        currency_code="PEN",
        supplier=Party(ruc="20131312955", doc_type_code="6", legal_name="SUNAT"),
        customer=Party(ruc="20100047218", doc_type_code="6", legal_name="BCP"),
    )
    inv.lines.append(InvoiceLine(
        line_id=1, description="Test", quantity=Decimal("1"),
        unit_price=Decimal("100"), line_extension_amount=Decimal("100"),
        igv_amount=Decimal("18"),
    ))
    inv.total_payable = Decimal("118")
    inv.total_tax_inclusive = Decimal("118")
    inv.total_tax_exclusive = Decimal("100")
    inv.total_line_extension = Decimal("100")
    inv.total_taxed = Decimal("100")
    inv.total_igv = Decimal("18")
    return UblInvoiceBuilder().build(inv)


@tagged("post_install", "-at_install", "l10n_pe_edi")
class TestXadesSigner(TransactionCase):

    def setUp(self):
        super().setUp()
        self.cert_pem, self.key_pem = _make_self_signed_pem()
        self.signer = XadesBesSigner(self.cert_pem, self.key_pem)

    # ─── Construcción ─────────────────────────────────────────────

    def test_init_requires_cert_and_key(self):
        with self.assertRaises(XadesSigningError):
            XadesBesSigner(b"", b"")
        with self.assertRaises(XadesSigningError):
            XadesBesSigner(self.cert_pem, b"")

    def test_from_pfx_bytes_works(self):
        pfx = _make_self_signed_pfx(password=b"123456")
        signer = XadesBesSigner.from_pfx_bytes(pfx, b"123456")
        self.assertIsNotNone(signer._key)

    def test_from_pfx_wrong_password_raises(self):
        pfx = _make_self_signed_pfx(password=b"123456")
        with self.assertRaises(Exception):
            XadesBesSigner.from_pfx_bytes(pfx, b"wrong-password")

    # ─── Sign ─────────────────────────────────────────────────────

    def test_sign_adds_signature_to_extension_content(self):
        root = _make_test_root_with_placeholder()
        signed = self.signer.sign(root, signature_id="SignatureSP")

        sig_el = signed.find(
            f".//{{{NS_DS}}}Signature"
        )
        self.assertIsNotNone(sig_el, "Falta nodo ds:Signature tras firmar")
        self.assertEqual(sig_el.get("Id"), "SignatureSP")

    def test_signature_has_signature_value(self):
        root = _make_test_root_with_placeholder()
        self.signer.sign(root)
        sig_value = root.findtext(f".//{{{NS_DS}}}SignatureValue")
        self.assertTrue(sig_value, "SignatureValue debe estar relleno tras firmar")
        # SHA-256 RSA-2048 → ~344 chars base64
        self.assertGreater(len(sig_value), 300)

    def test_signature_has_x509_certificate(self):
        root = _make_test_root_with_placeholder()
        self.signer.sign(root)
        cert = root.findtext(f".//{{{NS_DS}}}X509Certificate")
        self.assertTrue(cert, "X509Certificate debe estar embebido tras firmar")
        self.assertGreater(len(cert), 200)

    def test_sign_then_verify_passes(self):
        root = _make_test_root_with_placeholder()
        self.signer.sign(root)
        self.assertTrue(self.signer.verify(root))

    def test_verify_fails_with_different_signer(self):
        """Si firmo con un cert y verifico con otro, debe fallar."""
        root = _make_test_root_with_placeholder()
        self.signer.sign(root)

        other_cert, other_key = _make_self_signed_pem()
        other_signer = XadesBesSigner(other_cert, other_key)
        self.assertFalse(other_signer.verify(root))

    def test_sign_without_extension_placeholder_raises(self):
        """Si el árbol no tiene ext:UBLExtensions/UBLExtension/ExtensionContent,
        debemos fallar limpio."""
        from lxml import etree
        bare = etree.fromstring(b'<root xmlns="urn:test"/>')
        with self.assertRaises(XadesSigningError):
            self.signer.sign(bare)

    def test_sign_is_idempotent_on_multiple_calls(self):
        """Firmar 2 veces debe reemplazar la firma, no duplicarla."""
        root = _make_test_root_with_placeholder()
        self.signer.sign(root)
        self.signer.sign(root)
        sigs = root.findall(f".//{{{NS_DS}}}Signature")
        self.assertEqual(len(sigs), 1, "Solo debe haber 1 firma tras firmar 2 veces")
