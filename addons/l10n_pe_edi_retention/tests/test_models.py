# Copyright 2026 Marc Martínez & contributors
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_pe_edi_retention")
class TestRetentionModel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create({
            "name": "Test Ret Co",
            "country_id": cls.pe.id,
            "vat": "20131312955",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Sujeto Retenido SAC",
            "country_id": cls.pe.id,
        })

    def _make_retention(self):
        return self.env["l10n.pe.retention"].create({
            "name": "R001-1",
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "regime_code": "01",
            "regime_percent": 3.0,
        })

    def test_create_with_lines_computes_totals(self):
        ret = self._make_retention()
        self.env["l10n.pe.retention.line"].create({
            "retention_id": ret.id,
            "doc_type_code": "01",
            "doc_serie_number": "F001-123",
            "doc_issue_date": "2026-05-15",
            "doc_total_amount": 1180.0,
            "paid_amount": 1180.0,
            "paid_date": "2026-05-18",
            "retention_amount": 35.40,
            "retention_date": "2026-05-18",
        })
        self.env["l10n.pe.retention.line"].create({
            "retention_id": ret.id,
            "doc_type_code": "01",
            "doc_serie_number": "F001-124",
            "doc_issue_date": "2026-05-16",
            "doc_total_amount": 590.0,
            "paid_amount": 590.0,
            "paid_date": "2026-05-18",
            "retention_amount": 17.70,
            "retention_date": "2026-05-18",
        })
        ret.invalidate_recordset()
        self.assertAlmostEqual(ret.total_retention_amount, 53.10, places=2)
        self.assertAlmostEqual(ret.total_paid, 1770.0, places=2)

    def test_net_total_cashed_computed(self):
        ret = self._make_retention()
        line = self.env["l10n.pe.retention.line"].create({
            "retention_id": ret.id,
            "doc_type_code": "01",
            "doc_serie_number": "F001-200",
            "doc_issue_date": "2026-05-15",
            "doc_total_amount": 1000.0,
            "paid_amount": 1000.0,
            "paid_date": "2026-05-18",
            "retention_amount": 30.0,
            "retention_date": "2026-05-18",
        })
        line.invalidate_recordset()
        self.assertEqual(line.net_total_cashed, 970.0)

    def test_unique_name_per_company(self):
        self._make_retention()
        with self.assertRaisesRegex(Exception, "unique|UNIQUE"):
            self._make_retention()


@tagged("post_install", "-at_install", "l10n_pe_edi_retention")
class TestPerceptionModel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref("base.pe")
        cls.company = cls.env["res.company"].create({
            "name": "Test Per Co",
            "country_id": cls.pe.id,
            "vat": "20131312955",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Cliente Percibido SAC",
            "country_id": cls.pe.id,
        })

    def test_create_perception_with_lines(self):
        per = self.env["l10n.pe.perception"].create({
            "name": "P001-1",
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "regime_code": "01",
            "regime_percent": 2.0,
        })
        line = self.env["l10n.pe.perception.line"].create({
            "perception_id": per.id,
            "doc_type_code": "01",
            "doc_serie_number": "F001-456",
            "doc_issue_date": "2026-05-15",
            "doc_total_amount": 1180.0,
            "paid_amount": 1180.0,
            "paid_date": "2026-05-18",
            "perception_amount": 23.60,
            "perception_date": "2026-05-18",
        })
        line.invalidate_recordset()
        # total_cashed = paid + perception
        self.assertEqual(line.total_cashed, 1203.60)
        per.invalidate_recordset()
        self.assertAlmostEqual(per.total_perception_amount, 23.60, places=2)
        self.assertAlmostEqual(per.total_cashed, 1203.60, places=2)

    def test_perception_regime_selection_values(self):
        per = self.env["l10n.pe.perception"].create({
            "name": "P001-2",
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "regime_code": "03",  # importación
            "regime_percent": 5.0,
        })
        self.assertEqual(per.regime_code, "03")
        self.assertEqual(per.regime_percent, 5.0)
