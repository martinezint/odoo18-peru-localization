# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)
"""Firma XAdES-BES de XML UBL 2.1 para SUNAT.

SUNAT exige:
- C14N 1.0 (Canonical XML 1.0, sin comentarios)
- Algoritmo: RSA-SHA256
- La firma va dentro de ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent
- Reference URI="" (firma todo el documento) con transform enveloped-signature
- KeyInfo/X509Data con el certificado embebido

XAdES-BES = XML Advanced Electronic Signatures - Basic Electronic Signature.
"BES" significa que solo lleva el certificado, sin timestamps adicionales.

Usamos python-xmlsec (binding a libxmlsec1) porque es la implementación más
sólida en Python para XML Signature. signxml tiene problemas conocidos con C14N
y SUNAT en casos esquina.
"""

from __future__ import annotations

import logging
from pathlib import Path

import xmlsec
from lxml import etree

from .ubl_builder import NS_DS, NS_EXT

_logger = logging.getLogger(__name__)


class XadesSigningError(Exception):
    """Error específico al firmar/verificar — el caller decide cómo loggear."""


class XadesBesSigner:
    """Firma XAdES-BES un XML UBL preparado por UblInvoiceBuilder.

    Uso::

        signer = XadesBesSigner.from_pfx(pfx_path="/opt/odoo/certificates/dev.pfx",
                                          pfx_password=b"123456")
        root = builder.build(invoice)
        signed_root = signer.sign(root, signature_id="SignatureSP")
        xml_bytes = etree.tostring(signed_root, xml_declaration=True,
                                   encoding="UTF-8", standalone=False)
    """

    def __init__(self, cert_pem: bytes, key_pem: bytes, key_password: bytes | None = None):
        """Carga key + cert ya en formato PEM."""
        if not cert_pem or not key_pem:
            raise XadesSigningError("cert_pem y key_pem son obligatorios")
        self._key = xmlsec.Key.from_memory(
            key_pem,
            format=xmlsec.constants.KeyDataFormatPem,
            password=key_password,
        )
        self._key.load_cert_from_memory(
            cert_pem,
            format=xmlsec.constants.KeyDataFormatCertPem,
        )

    # ─── Factory methods ─────────────────────────────────────────────

    @classmethod
    def from_pfx(cls, pfx_path: str | Path, pfx_password: bytes) -> XadesBesSigner:
        """Carga desde archivo PKCS#12 (.pfx/.p12)."""
        pfx_bytes = Path(pfx_path).read_bytes()
        return cls.from_pfx_bytes(pfx_bytes, pfx_password)

    @classmethod
    def from_pfx_bytes(cls, pfx_bytes: bytes, pfx_password: bytes) -> XadesBesSigner:
        """Extrae key + cert del PKCS#12 vía cryptography (puro Python) y los
        pasa a xmlsec en formato PEM."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.serialization import pkcs12

        private_key, certificate, _additional = pkcs12.load_key_and_certificates(
            pfx_bytes, pfx_password
        )
        if certificate is None or private_key is None:
            raise XadesSigningError("El PFX no contiene par clave/cert válido.")
        cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return cls(cert_pem=cert_pem, key_pem=key_pem)

    # ─── Sign / Verify ───────────────────────────────────────────────

    def sign(self, root: etree._Element, signature_id: str = "SignatureSP") -> etree._Element:
        """Inserta y firma. Modifica el árbol in-place y lo devuelve.

        La firma se inserta en ``ext:UBLExtensions/ext:UBLExtension[1]/ext:ExtensionContent``.
        Si no hay un ExtensionContent vacío, lanza XadesSigningError.
        """
        ext_content = self._find_extension_content(root)
        signature_tpl = self._build_signature_template(signature_id)
        ext_content.append(signature_tpl)

        ctx = xmlsec.SignatureContext()
        ctx.key = self._key
        try:
            ctx.sign(signature_tpl)
        except xmlsec.Error as exc:
            raise XadesSigningError(f"xmlsec.sign falló: {exc}") from exc
        return root

    def verify(self, root: etree._Element) -> bool:
        """Verifica la firma. Devuelve True si pasa, False si falla."""
        sig_node = xmlsec.tree.find_node(root, xmlsec.constants.NodeSignature)
        if sig_node is None:
            raise XadesSigningError("No hay nodo <ds:Signature> en el XML")
        ctx = xmlsec.SignatureContext()
        ctx.key = self._key
        try:
            ctx.verify(sig_node)
            return True
        except xmlsec.Error:
            return False

    # ─── Internos ────────────────────────────────────────────────────

    def _find_extension_content(self, root) -> etree._Element:
        """Localiza el ext:ExtensionContent del primer UBLExtension."""
        path = f"{{{NS_EXT}}}UBLExtensions/{{{NS_EXT}}}UBLExtension/{{{NS_EXT}}}ExtensionContent"
        ext_content = root.find(path)
        if ext_content is None:
            raise XadesSigningError(
                "Estructura UBL inválida: falta ext:UBLExtensions/UBLExtension/ExtensionContent. "
                "Asegúrate de usar UblInvoiceBuilder que crea el placeholder."
            )
        # Limpieza: si ya tiene contenido, lo quitamos para no duplicar firmas.
        for child in list(ext_content):
            ext_content.remove(child)
        return ext_content

    def _build_signature_template(self, signature_id: str) -> etree._Element:
        """Plantilla ds:Signature estilo SUNAT.

        SignatureMethod = RSA-SHA256
        CanonicalizationMethod = C14N 1.0
        Reference URI = "" (firma todo el documento) con transform enveloped-signature
        + transform C14N
        KeyInfo/X509Data: cert se embebe automáticamente al sign().
        """
        sig = etree.Element(f"{{{NS_DS}}}Signature", attrib={"Id": signature_id})
        signed_info = etree.SubElement(sig, f"{{{NS_DS}}}SignedInfo")
        etree.SubElement(
            signed_info,
            f"{{{NS_DS}}}CanonicalizationMethod",
            Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        )
        etree.SubElement(
            signed_info,
            f"{{{NS_DS}}}SignatureMethod",
            Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
        )
        ref = etree.SubElement(signed_info, f"{{{NS_DS}}}Reference", URI="")
        transforms = etree.SubElement(ref, f"{{{NS_DS}}}Transforms")
        etree.SubElement(
            transforms,
            f"{{{NS_DS}}}Transform",
            Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature",
        )
        etree.SubElement(
            ref,
            f"{{{NS_DS}}}DigestMethod",
            Algorithm="http://www.w3.org/2001/04/xmlenc#sha256",
        )
        etree.SubElement(ref, f"{{{NS_DS}}}DigestValue")
        etree.SubElement(sig, f"{{{NS_DS}}}SignatureValue")
        key_info = etree.SubElement(sig, f"{{{NS_DS}}}KeyInfo")
        x509_data = etree.SubElement(key_info, f"{{{NS_DS}}}X509Data")
        etree.SubElement(x509_data, f"{{{NS_DS}}}X509Certificate")
        return sig
