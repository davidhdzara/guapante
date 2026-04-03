# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderDeliveryStatus(TransactionCase):
    """Tests for sale.order guapante_delivery_status compute logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse Guapante',
                'code': 'TWG',
                'company_id': cls.env.company.id,
            })
        cls.warehouse.delivery_steps = 'pick_ship'
        
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner Guapante',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Aguacate Hass Test',
            'type': 'consu',
            'list_price': 5000.0,
        })

    def _create_confirmed_order(self):
        """Helper: create and confirm a sale order."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 10,
            })],
        })
        order.action_confirm()
        return order

    def test_default_status_received(self):
        """A confirmed order with no pickings processed should be 'received'."""
        order = self._create_confirmed_order()
        self.assertEqual(
            order.guapante_delivery_status,
            'received',
            "Default delivery status should be 'received' after confirmation",
        )

    def test_status_preparing_when_assigned(self):
        """When validation & weighing starts (quantity > 0), status should be 'preparing'."""
        order = self._create_confirmed_order()
        pickings = order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'internal')
        if pickings:
            # Force assignment and simulate weighing
            for picking in pickings:
                picking.action_assign()
                # In Odoo 18, we just write the quantity to the move
                for move in picking.move_ids:
                    move.write({'quantity': 1})
            order.invalidate_recordset(['guapante_delivery_status'])
            self.assertEqual(
                order.guapante_delivery_status,
                'preparing',
                "Status should be 'preparing' when internal picking has quantities done (weighing starts)",
            )

    def test_status_shipping_when_done(self):
        """When pickings are done (internal transferred), ship is assigned, status should be 'shipping'."""
        order = self._create_confirmed_order()
        pickings = order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'internal')
        if pickings:
            for picking in pickings:
                picking.action_assign()
                # Set quantities done and validate
                for move in picking.move_ids:
                    move.quantity = move.product_uom_qty
                picking.button_validate()
            order.invalidate_recordset(['guapante_delivery_status'])
            self.assertEqual(
                order.guapante_delivery_status,
                'shipping',
                "Status should be 'shipping' when internal picking is done and outgoing is assigned",
            )


@tagged('post_install', '-at_install')
class TestCartUpdateFractional(TransactionCase):
    """Tests for sale.order._cart_update with fractional quantities."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner Cart',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Papa Capira Test',
            'type': 'consu',
            'list_price': 3000.0,
        })

    def test_integer_quantity_unchanged(self):
        """Integer quantities should pass through to standard logic without modification."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        result = order._cart_update(
            product_id=self.product.id,
            add_qty=5,
        )
        self.assertTrue(result.get('line_id'), "A line should be created")
        line = self.env['sale.order.line'].browse(result['line_id'])
        self.assertEqual(line.product_uom_qty, 5.0)

    def test_fractional_add_qty(self):
        """Adding a fractional quantity (e.g. 0.5 kg) should create a line with that exact qty."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        result = order._cart_update(
            product_id=self.product.id,
            add_qty=0.5,
        )
        self.assertTrue(result.get('line_id'), "A line should be created for fractional qty")
        line = self.env['sale.order.line'].browse(result['line_id'])
        self.assertAlmostEqual(
            line.product_uom_qty, 0.5, places=2,
            msg="Fractional quantity should be preserved exactly",
        )

    def test_fractional_set_qty(self):
        """Setting a fractional quantity should result in that exact qty on the line."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        # First add an integer qty
        result = order._cart_update(
            product_id=self.product.id,
            add_qty=1,
        )
        line_id = result.get('line_id')
        # Now set to 0.75
        result = order._cart_update(
            product_id=self.product.id,
            line_id=line_id,
            set_qty=0.75,
        )
        line = self.env['sale.order.line'].browse(result['line_id'])
        self.assertAlmostEqual(
            line.product_uom_qty, 0.75, places=2,
            msg="set_qty=0.75 should result in exactly 0.75",
        )


@tagged('post_install', '-at_install')
class TestDailySequence(TransactionCase):
    """Tests for sale.order _assign_daily_sequences (ir.sequence-backed)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1
        )
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse DailySeq',
                'code': 'TWD',
                'company_id': cls.env.company.id,
            })
        cls.warehouse.delivery_steps = 'pick_ship'
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner DailySeq',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Product DailySeq',
            'type': 'consu',
            'list_price': 1000.0,
        })

    def _create_confirmed_order(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        order.action_confirm()
        return order

    def _set_pickings_scheduled_date(self, orders, delivery_date):
        dt = fields.Datetime.to_datetime(delivery_date)
        for order in orders:
            for picking in order.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel')
            ):
                picking.scheduled_date = dt

    def test_assign_daily_sequence_unique_increment(self):
        """New orders on the same delivery day get distinct positive consecutive numbers."""
        o1 = self._create_confirmed_order()
        o2 = self._create_confirmed_order()
        d = fields.Date.add(fields.Date.context_today(self.env['sale.order']), days=14)
        self._set_pickings_scheduled_date((o1, o2), d)
        o1.daily_sequence = 0
        o2.daily_sequence = 0
        self.env['sale.order'].sudo()._assign_daily_sequences(d)
        self.assertGreater(o1.daily_sequence, 0)
        self.assertGreater(o2.daily_sequence, 0)
        self.assertNotEqual(o1.daily_sequence, o2.daily_sequence)

    def test_assign_respects_existing_daily_sequence(self):
        """Existing non-zero daily_sequence is kept; next free order continues after max."""
        o1 = self._create_confirmed_order()
        o2 = self._create_confirmed_order()
        d = fields.Date.add(fields.Date.context_today(self.env['sale.order']), days=21)
        self._set_pickings_scheduled_date((o1, o2), d)
        o1.daily_sequence = 50
        o2.daily_sequence = 0
        self.env['sale.order'].sudo()._assign_daily_sequences(d)
        self.assertEqual(o1.daily_sequence, 50)
        self.assertEqual(o2.daily_sequence, 51)
