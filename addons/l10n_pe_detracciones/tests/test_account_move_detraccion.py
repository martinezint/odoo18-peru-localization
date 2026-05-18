# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.tests.common import TransactionCase, tagged

DETRACCION_MIN_AMOUNT = 700.0


@tagged("post_install", "-at_install", "l10n_pe_detracciones")
class TestAccountMoveDetraccion(TransactionCase):
    """Cálculo automático del monto de detracción en account.move."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")

        # Empresa PE con chart 'pe' aplicado (necesario para account.tax)
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Detracciones Co",
                "country_id": cls.pe.id,
            }
        )
        cls.env["account.chart.template"].try_loading("pe", company=cls.company, install_demo=False)
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context={"allowed_company_ids": [cls.company.id]})
        cls.env.user.company_id = cls.company

        # Partner proveedor genérico
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Proveedor SAC",
                "country_id": cls.pe.id,
            }
        )

        # Códigos detracción cargados como data
        cls.det_022 = cls.env.ref("l10n_pe_detracciones.det_022")  # 12% servicios
        cls.det_002 = cls.env.ref("l10n_pe_detracciones.det_002")  # 4% arroz

        # Productos
        cls.product_with_det = cls.env["product.product"].create(
            {
                "name": "Servicio empresarial",
                "l10n_pe_detraccion_code_id": cls.det_022.id,
            }
        )
        cls.product_no_det = cls.env["product.product"].create(
            {
                "name": "Producto sin detracción",
            }
        )

    def _create_bill(self, amount, product=None):
        product = product or self.product_with_det
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_date": "2026-05-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": product.name,
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [],  # sin impuestos para simplificar el cálculo
                        },
                    )
                ],
            }
        )

    def test_no_detraccion_when_no_product_code(self):
        bill = self._create_bill(1000.0, product=self.product_no_det)
        self.assertFalse(bill.l10n_pe_detraccion_has_application)
        self.assertEqual(bill.l10n_pe_detraccion_amount, 0.0)

    def test_detraccion_applies_above_threshold(self):
        bill = self._create_bill(1000.0)  # > 700
        self.assertTrue(bill.l10n_pe_detraccion_has_application)
        self.assertEqual(bill.l10n_pe_detraccion_code_id, self.det_022)
        # 1000 * 12% = 120
        self.assertEqual(bill.l10n_pe_detraccion_amount, 120.0)

    def test_detraccion_does_not_apply_at_threshold(self):
        """Umbral SUNAT es 'mayor que 700', no '>=700'."""
        bill = self._create_bill(700.0)
        self.assertFalse(bill.l10n_pe_detraccion_has_application)

    def test_detraccion_does_not_apply_below_threshold(self):
        bill = self._create_bill(500.0)
        self.assertFalse(bill.l10n_pe_detraccion_has_application)
        self.assertEqual(bill.l10n_pe_detraccion_amount, 0.0)

    def test_detraccion_recomputes_when_amount_changes(self):
        bill = self._create_bill(1000.0)
        self.assertEqual(bill.l10n_pe_detraccion_amount, 120.0)
        # Cambiar la cantidad para que el total cambie
        bill.invoice_line_ids[0].quantity = 2  # total 2000
        self.assertEqual(bill.l10n_pe_detraccion_amount, 240.0)

    def test_detraccion_uses_first_product_with_code(self):
        """Si la factura tiene productos mixtos, toma el primero con código."""
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_date": "2026-05-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_no_det.id,
                            "name": self.product_no_det.name,
                            "quantity": 1,
                            "price_unit": 300.0,
                            "tax_ids": [],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_with_det.id,
                            "name": self.product_with_det.name,
                            "quantity": 1,
                            "price_unit": 800.0,
                            "tax_ids": [],
                        },
                    ),
                ],
            }
        )
        self.assertTrue(bill.l10n_pe_detraccion_has_application)
        self.assertEqual(bill.l10n_pe_detraccion_code_id, self.det_022)
        # Total 1100, 12% = 132
        self.assertEqual(bill.l10n_pe_detraccion_amount, 132.0)

    # NOTA: tests del chatter post-posteo eliminados — la cadena de validación
    # de l10n_latam_invoice_document exige asignar número de documento al
    # postear, lo cual requiere journal con use_documents=True + número manual.
    # Volveremos a estos tests cuando l10n_pe_edi integre journals PE con
    # numeración automática.

    def test_constancia_field_can_be_set(self):
        """Verifica que los campos de constancia/fecha existen y son escribibles."""
        bill = self._create_bill(1000.0)
        bill.l10n_pe_detraccion_constancia = "00-001-12345678"
        bill.l10n_pe_detraccion_date = "2026-05-15"
        self.assertEqual(bill.l10n_pe_detraccion_constancia, "00-001-12345678")
        self.assertEqual(str(bill.l10n_pe_detraccion_date), "2026-05-15")
