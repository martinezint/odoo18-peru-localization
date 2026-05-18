# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

import base64

from odoo.tests.common import TransactionCase, tagged


SIGNED_XML_SAMPLE = """<?xml version="1.0"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
         xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
  <ext:UBLExtensions>
    <ext:UBLExtension>
      <ext:ExtensionContent>
        <ds:Signature Id="SignatureSP">
          <ds:SignedInfo>
            <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
            <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
            <ds:Reference URI="">
              <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
              <ds:DigestValue>EXPECTED_DIGEST_FROM_XAdES</ds:DigestValue>
            </ds:Reference>
          </ds:SignedInfo>
          <ds:SignatureValue>EXPECTED_SIGNATURE_VALUE_BASE64==</ds:SignatureValue>
        </ds:Signature>
      </ext:ExtensionContent>
    </ext:UBLExtension>
  </ext:UBLExtensions>
</Invoice>
""".encode("utf-8")


@tagged("post_install", "-at_install", "l10n_pe_reports_pdf")
class TestSignatureExtraction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Setup mínimo para crear un l10n.pe.edi.document
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create({
            "name": "Test PDF Co",
            "country_id": cls.pe.id,
            "vat": "20131312955",
        })
        cls.env["account.chart.template"].try_loading(
            "pe", company=cls.company, install_demo=False
        )
        cls.partner = cls.env["res.partner"].create({
            "name": "Cliente",
            "country_id": cls.pe.id,
        })
        cls.move = cls.env["account.move"].with_company(cls.company).create({
            "move_type": "out_invoice",
            "partner_id": cls.partner.id,
            "company_id": cls.company.id,
            "invoice_line_ids": [(0, 0, {
                "name": "X", "quantity": 1, "price_unit": 100.0, "tax_ids": [],
            })],
        })

    def _make_doc(self, xml_bytes=None):
        return self.env["l10n.pe.edi.document"].create({
            "move_id": self.move.id,
            "name": "test.xml",
            "xml_signed": base64.b64encode(xml_bytes) if xml_bytes else False,
            "state": "signed" if xml_bytes else "draft",
        })

    def test_extract_signature_value(self):
        doc = self._make_doc(SIGNED_XML_SAMPLE)
        sig = doc._extract_signature_value()
        self.assertEqual(sig, "EXPECTED_SIGNATURE_VALUE_BASE64==")

    def test_no_xml_returns_empty(self):
        doc = self._make_doc(xml_bytes=None)
        self.assertEqual(doc._extract_signature_value(), "")

    def test_malformed_xml_returns_empty(self):
        doc = self._make_doc(b"<not closed")
        self.assertEqual(doc._extract_signature_value(), "")

    def test_xml_without_signature_returns_empty(self):
        doc = self._make_doc(b"<Invoice xmlns=\"urn:test\"><a/></Invoice>")
        self.assertEqual(doc._extract_signature_value(), "")

    def test_signature_value_with_newlines_normalized(self):
        xml_multiline = """<?xml version="1.0"?>
<Invoice xmlns="urn:test" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
  <ds:Signature>
    <ds:SignatureValue>LINE1
LINE2
LINE3==</ds:SignatureValue>
  </ds:Signature>
</Invoice>
""".encode("utf-8")
        doc = self._make_doc(xml_multiline)
        # newlines stripped
        self.assertEqual(doc._extract_signature_value(), "LINE1LINE2LINE3==")
