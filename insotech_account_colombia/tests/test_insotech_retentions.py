from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestInsotechRetentions(TransactionCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.uvt_model = cls.env['insotech.uvt']
        cls.concept_model = cls.env['insotech.retention.concept']
        cls.company = cls.env.company

        # Cuenta contable de test
        cls.test_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.id),
            ('deprecated', '=', False),
        ], limit=1)
        if not cls.test_account:
            cls.test_account = cls.env['account.account'].create({
                'code': '135599',
                'name': 'Cuenta Test Retenciones',
                'account_type': 'asset_current',
                'company_ids': [(4, cls.company.id)],
            })

        # UVT de prueba
        cls.uvt_2026 = cls.uvt_model.create({
            'year': 2026,
            'value': 52374.0,
        })

        # Tax de compra para tests
        cls.purchase_tax = cls.env['account.tax'].create({
            'name': 'Test 2.5% RteFte Compra',
            'amount': -2.5,
            'amount_type': 'percent',
            'type_tax_use': 'purchase',
        })

        # Concepto de retención con dirección compra
        cls.concept_purchase = cls.concept_model.create({
            'name': 'Test RteFte Compras 2.5%',
            'type': 'retefuente',
            'direction': 'purchase',
            'base_uvt': 27.0,
            'percentage': 2.5,
            'account_id': cls.test_account.id,
            'purchase_tax_id': cls.purchase_tax.id,
        })

        # Proveedor normal (sin obligaciones especiales)
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Proveedor Test Normal',
            'supplier_rank': 1,
            'insotech_retention_concept_ids': [
                (4, cls.concept_purchase.id),
            ],
        })

    def test_01_uvt_creation_and_compute(self) -> None:
        """Prueba la correcta creación de una UVT y su nombre computado."""
        self.assertEqual(self.uvt_2026.name, 'UVT 2026')
        self.assertEqual(self.uvt_2026.value, 52374.0)

    def test_02_uvt_unique_constraint(self) -> None:
        """Prueba que no se puedan crear dos UVTs para el mismo año."""
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.uvt_model.create({
                    'year': 2026,
                    'value': 55000.0,
                })

    def test_03_concept_creation(self) -> None:
        """Prueba la creación de un concepto con los campos nuevos."""
        self.assertTrue(self.concept_purchase.id)
        self.assertEqual(self.concept_purchase.direction, 'purchase')
        self.assertEqual(self.concept_purchase.percentage, 2.5)
        self.assertTrue(self.concept_purchase.purchase_tax_id)

    def test_04_calculate_retentions_applies_tax(self) -> None:
        """Factura de proveedor: el botón inyecta el tax de compra."""
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': '2026-03-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'Compra test',
                'quantity': 1,
                'price_unit': 5000000,
            })],
        })
        result = invoice.action_calculate_retentions()
        self.assertTrue(invoice.insotech_retention_calculated)
        applied_taxes = invoice.invoice_line_ids.mapped('tax_ids')
        self.assertIn(self.purchase_tax, applied_taxes)

    def test_05_autoretenedor_blocks_retention(self) -> None:
        """Proveedor con O-15 no debe recibir retención."""
        o15 = self.env['l10n_co_edi.type_code'].search(
            [('name', '=', 'O-15')], limit=1,
        )
        if not o15:
            return  # Skip si no hay datos DIAN en la BD de test
        vendor_auto = self.env['res.partner'].create({
            'name': 'Proveedor Autorretenedor',
            'supplier_rank': 1,
            'l10n_co_edi_obligation_type_ids': [(4, o15.id)],
            'insotech_retention_concept_ids': [
                (4, self.concept_purchase.id),
            ],
        })
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': vendor_auto.id,
            'invoice_date': '2026-03-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'Compra test',
                'quantity': 1,
                'price_unit': 5000000,
            })],
        })
        result = invoice.action_calculate_retentions()
        self.assertFalse(invoice.insotech_retention_calculated)

    def test_06_base_below_uvt_no_retention(self) -> None:
        """Base inferior al mínimo UVT no genera retención."""
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': '2026-03-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'Compra pequeña',
                'quantity': 1,
                'price_unit': 1000,  # << Muy bajo, no supera 27 UVT
            })],
        })
        result = invoice.action_calculate_retentions()
        self.assertFalse(invoice.insotech_retention_calculated)
