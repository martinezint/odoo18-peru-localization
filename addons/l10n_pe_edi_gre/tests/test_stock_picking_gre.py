# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_edi_gre")
class TestStockPickingGre(TransactionCase):
    """Tests del modelo (validaciones + fields). No prueba el XML build E2E
    porque requiere setup completo de stock (warehouses, ubicaciones, etc.)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.partner = cls.env["res.partner"].create({
            "name": "Cliente GRE",
            "country_id": cls.pe.id,
            "vat": "20100047218",
        })

    def _new_picking(self, **vals):
        # Usamos un picking_type ya existente (cualquier outgoing del sistema)
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "outgoing"),
        ], limit=1)
        defaults = {
            "partner_id": self.partner.id,
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
        }
        defaults.update(vals)
        return self.env["stock.picking"].create(defaults)

    # ─── Constraints ─────────────────────────────────────────────

    def test_origin_ubigeo_must_be_6_digits(self):
        with self.assertRaisesRegex(UserError, "6 dígitos"):
            self._new_picking(l10n_pe_gre_origin_ubigeo="12345")

    def test_origin_ubigeo_must_be_numeric(self):
        with self.assertRaisesRegex(UserError, "6 dígitos"):
            self._new_picking(l10n_pe_gre_origin_ubigeo="ABC123")

    def test_destination_ubigeo_must_be_6_digits(self):
        with self.assertRaisesRegex(UserError, "6 dígitos"):
            self._new_picking(l10n_pe_gre_destination_ubigeo="123")

    def test_valid_ubigeos_accepted(self):
        picking = self._new_picking(
            l10n_pe_gre_origin_ubigeo="150122",
            l10n_pe_gre_destination_ubigeo="150101",
        )
        self.assertTrue(picking.id)

    def test_empty_ubigeo_ok(self):
        # Vacío no debe disparar — sólo cuando se quiera generar GRE se
        # validará vía _l10n_pe_gre_validate_required.
        picking = self._new_picking()
        self.assertFalse(picking.l10n_pe_gre_origin_ubigeo)

    # ─── Fields defaults ─────────────────────────────────────────

    def test_default_transport_mode_privado(self):
        picking = self._new_picking()
        # Default = '02' privado (sin carrier_id necesario)
        self.assertEqual(picking.l10n_pe_gre_transport_mode, "02")

    def test_default_driver_doc_type_dni(self):
        picking = self._new_picking()
        self.assertEqual(picking.l10n_pe_gre_driver_doc_type, "1")

    def test_default_total_packages_1(self):
        picking = self._new_picking()
        self.assertEqual(picking.l10n_pe_gre_total_packages, 1)

    # ─── validate_required ───────────────────────────────────────

    def test_validate_required_missing_motivo_raises(self):
        picking = self._new_picking()
        # Sin motivo_traslado y otros campos → error con todos los faltantes
        with self.assertRaisesRegex(UserError, "Faltan datos obligatorios"):
            picking._l10n_pe_gre_validate_required()

    def test_validate_required_with_all_fields_passes(self):
        # Asignamos RUC y cert al company
        self.env.company.vat = "20131312955"
        picking = self._new_picking(
            l10n_pe_gre_motivo_traslado="01",
            l10n_pe_gre_transport_mode="02",
            l10n_pe_gre_license_plate="ABC-123",
            l10n_pe_gre_driver_doc_number="12345678",
            l10n_pe_gre_origin_ubigeo="150122",
            l10n_pe_gre_destination_ubigeo="150101",
        )
        # No debe lanzar
        try:
            picking._l10n_pe_gre_validate_required()
        except UserError as exc:
            self.fail(f"validate_required no debió lanzar: {exc}")
