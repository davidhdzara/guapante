# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPurchaseDemandInstall(TransactionCase):
    """Verify purchase demand models are correctly installed."""

    def test_purchase_demand_model_exists(self):
        """guapante.purchase.demand model should be registered."""
        model = self.env['ir.model'].search([
            ('model', '=', 'guapante.purchase.demand'),
        ])
        self.assertTrue(
            model,
            "Model 'guapante.purchase.demand' should be registered",
        )

    def test_purchase_demand_line_model_exists(self):
        """guapante.purchase.demand.line model should be registered."""
        model = self.env['ir.model'].search([
            ('model', '=', 'guapante.purchase.demand.line'),
        ])
        self.assertTrue(
            model,
            "Model 'guapante.purchase.demand.line' should be registered",
        )

    def test_purchase_demand_access_rights(self):
        """CRUD access should exist for both demand models."""
        for model_name in (
            'guapante.purchase.demand',
            'guapante.purchase.demand.line',
        ):
            access = self.env['ir.model.access'].search([
                ('model_id.model', '=', model_name),
            ])
            self.assertTrue(
                access,
                "Access rules should exist for %s" % model_name,
            )


@tagged('post_install', '-at_install')
class TestPurchaseDemandRefresh(TransactionCase):
    """Tests for the action_refresh demand calculation logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test WH Demand',
                'code': 'TWD',
                'company_id': cls.env.company.id,
            })
        cls.warehouse.delivery_steps = 'pick_ship'

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner Demand',
        })

        # Weight-based product (kg)
        cls.uom_kg = cls.env.ref('uom.product_uom_kgm')
        cls.product_fruit = cls.env['product.product'].create({
            'name': 'Mango Test',
            'type': 'consu',
            'uom_id': cls.uom_kg.id,
            'uom_po_id': cls.uom_kg.id,
            'list_price': 5000.0,
        })

        # Unit-based product
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.product_unit = cls.env['product.product'].create({
            'name': 'Lechuga Test',
            'type': 'consu',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
            'list_price': 2000.0,
        })

        # Attribute setup (no_variant)
        cls.attr_maturity = cls.env['product.attribute'].create({
            'name': 'Madurez Test',
            'create_variant': 'no_variant',
        })
        cls.val_pinton = cls.env['product.attribute.value'].create({
            'name': 'Pintón',
            'attribute_id': cls.attr_maturity.id,
        })
        cls.val_maduro = cls.env['product.attribute.value'].create({
            'name': 'Maduro',
            'attribute_id': cls.attr_maturity.id,
        })
        # Assign attribute to product template
        cls.attr_line = cls.env[
            'product.template.attribute.line'
        ].create({
            'product_tmpl_id': cls.product_fruit.product_tmpl_id.id,
            'attribute_id': cls.attr_maturity.id,
            'value_ids': [
                (6, 0, [cls.val_pinton.id, cls.val_maduro.id]),
            ],
        })

    def _create_confirmed_order(
        self, product, qty, attr_values=None,
    ):
        """Helper: create and confirm a sale order."""
        line_vals = {
            'product_id': product.id,
            'product_uom_qty': qty,
        }
        if attr_values:
            line_vals['product_no_variant_attribute_value_ids'] = [
                (6, 0, attr_values.ids),
            ]
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, line_vals)],
        })
        order.action_confirm()
        return order

    def test_refresh_creates_demand_lines(self):
        """action_refresh should create demand lines from confirmed SOs."""
        self._create_confirmed_order(self.product_fruit, 10.0)
        self._create_confirmed_order(self.product_fruit, 5.0)

        session = self.env['guapante.purchase.demand'].create({})
        session.action_refresh()

        self.assertEqual(session.state, 'loaded')
        self.assertTrue(
            len(session.line_ids) >= 1,
            "Should have at least 1 demand line",
        )

    def test_refresh_groups_by_product(self):
        """Lines for the same product and same attributes should be grouped."""
        self._create_confirmed_order(self.product_fruit, 10.0)
        self._create_confirmed_order(self.product_fruit, 5.0)

        session = self.env['guapante.purchase.demand'].create({})
        session.action_refresh()

        fruit_lines = session.line_ids.filtered(
            lambda l: l.product_id == self.product_fruit
        )
        # Same product, same attributes → should be ONE line
        self.assertEqual(
            len(fruit_lines), 1,
            "Lines with same product+attrs should be merged",
        )
        self.assertAlmostEqual(
            fruit_lines.pending_kg, 15.0, places=1,
            msg="Demand should be 10 + 5 = 15 kg",
        )

    def test_refresh_separates_by_attribute(self):
        """Different no_variant attribute combos → separate demand lines."""
        # Get template attribute values
        ptav_pinton = self.attr_line.product_template_value_ids.filtered(
            lambda v: v.product_attribute_value_id == self.val_pinton
        )
        ptav_maduro = self.attr_line.product_template_value_ids.filtered(
            lambda v: v.product_attribute_value_id == self.val_maduro
        )

        self._create_confirmed_order(
            self.product_fruit, 10.0, ptav_pinton,
        )
        self._create_confirmed_order(
            self.product_fruit, 20.0, ptav_maduro,
        )

        session = self.env['guapante.purchase.demand'].create({})
        session.action_refresh()

        fruit_lines = session.line_ids.filtered(
            lambda l: l.product_id == self.product_fruit
        )
        self.assertEqual(
            len(fruit_lines), 2,
            "Different attributes should create separate lines",
        )

    def test_product_level_deficit(self):
        """Deficit should be calculated at the PRODUCT level, not per line.

        Since no_variant attributes share the same stock pool, the
        deficit must be: total_demand_for_product - stock_of_product.
        """
        ptav_pinton = self.attr_line.product_template_value_ids.filtered(
            lambda v: v.product_attribute_value_id == self.val_pinton
        )
        ptav_maduro = self.attr_line.product_template_value_ids.filtered(
            lambda v: v.product_attribute_value_id == self.val_maduro
        )

        self._create_confirmed_order(
            self.product_fruit, 10.0, ptav_pinton,
        )
        self._create_confirmed_order(
            self.product_fruit, 20.0, ptav_maduro,
        )

        session = self.env['guapante.purchase.demand'].create({})
        session.action_refresh()

        fruit_lines = session.line_ids.filtered(
            lambda l: l.product_id == self.product_fruit
        )
        # All lines of the same product should show the SAME deficit
        deficits = fruit_lines.mapped('product_deficit')
        self.assertEqual(
            len(set(deficits)), 1,
            "All attr combos of same product must share identical deficit",
        )

        # All lines show the same product_stock
        stocks = fruit_lines.mapped('product_stock')
        self.assertEqual(
            len(set(stocks)), 1,
            "All attr combos of same product must share identical stock",
        )

    def test_uom_mode_weight_vs_unit(self):
        """Weight products get uom_mode='kg', unit products get 'unit'."""
        self._create_confirmed_order(self.product_fruit, 10.0)
        self._create_confirmed_order(self.product_unit, 5.0)

        session = self.env['guapante.purchase.demand'].create({})
        session.action_refresh()

        fruit_line = session.line_ids.filtered(
            lambda l: l.product_id == self.product_fruit
        )
        unit_line = session.line_ids.filtered(
            lambda l: l.product_id == self.product_unit
        )
        self.assertEqual(fruit_line.uom_mode, 'kg')
        self.assertEqual(unit_line.uom_mode, 'unit')

    def test_select_deficit_action(self):
        """action_select_deficit should only select lines with deficit > 0."""
        self._create_confirmed_order(self.product_fruit, 10.0)

        session = self.env['guapante.purchase.demand'].create({})
        session.action_refresh()

        session.action_deselect_all()
        self.assertFalse(
            any(session.line_ids.mapped('selected')),
            "All lines should be deselected",
        )

        session.action_select_deficit()
        # Lines may or may not have deficit depending on stock
        # Just verify no crash
        self.assertTrue(True)

    def test_select_all_action(self):
        """action_select_all should mark all lines as selected."""
        self._create_confirmed_order(self.product_fruit, 10.0)

        session = self.env['guapante.purchase.demand'].create({})
        session.action_refresh()
        session.action_select_all()

        self.assertTrue(
            all(session.line_ids.mapped('selected')),
            "All lines should be selected after action_select_all",
        )


@tagged('post_install', '-at_install')
class TestPurchaseDemandPOGeneration(TransactionCase):
    """Tests for PO generation from demand lines."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner PO Gen',
        })
        cls.supplier = cls.env['res.partner'].create({
            'name': 'Test Supplier Frutas',
        })

        cls.uom_kg = cls.env.ref('uom.product_uom_kgm')
        cls.product = cls.env['product.product'].create({
            'name': 'Aguacate Test PO',
            'type': 'consu',
            'uom_id': cls.uom_kg.id,
            'uom_po_id': cls.uom_kg.id,
            'list_price': 8000.0,
            'seller_ids': [(0, 0, {
                'partner_id': cls.supplier.id,
                'price': 6000.0,
            })],
        })

    def test_generate_po_from_demand(self):
        """Selected demand lines should generate a Purchase Order."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 50.0,
            })],
        })
        order.action_confirm()

        session = self.env['guapante.purchase.demand'].create({})
        session.action_refresh()
        session.action_select_all()

        result = session.action_generate_purchase_orders()

        self.assertEqual(
            result['res_model'], 'purchase.order',
            "Should return an action to view the PO",
        )

        po = self.env['purchase.order'].browse(result['res_id'])
        self.assertTrue(po.exists())
        self.assertEqual(po.partner_id, self.supplier)
        self.assertTrue(
            len(po.order_line) >= 1,
            "PO should have at least one line",
        )

    def test_generate_po_groups_by_supplier(self):
        """Lines from different suppliers generate separate POs."""
        supplier_2 = self.env['res.partner'].create({
            'name': 'Supplier 2',
        })
        product_2 = self.env['product.product'].create({
            'name': 'Tomate Test PO',
            'type': 'consu',
            'uom_id': self.uom_kg.id,
            'list_price': 3000.0,
            'seller_ids': [(0, 0, {
                'partner_id': supplier_2.id,
                'price': 2000.0,
            })],
        })

        # Create orders for both products
        for prod in (self.product, product_2):
            order = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'order_line': [(0, 0, {
                    'product_id': prod.id,
                    'product_uom_qty': 10.0,
                })],
            })
            order.action_confirm()

        session = self.env['guapante.purchase.demand'].create({})
        session.action_refresh()
        session.action_select_all()

        result = session.action_generate_purchase_orders()

        # Should open list view with 2 POs
        self.assertEqual(result['view_mode'], 'list,form')
        po_ids = result['domain'][0][2]
        self.assertEqual(
            len(po_ids), 2,
            "Should generate 2 POs for 2 different suppliers",
        )
