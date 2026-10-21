# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDailySequence(TransactionCase):
    """Tests for sale.order _assign_daily_sequences (ir.sequence-backed).

    Movido de theme_guapante/tests/test_sale_order.py (2026-10-21) junto con el
    subsistema de "Caja #" — ver models/sale_order.py de este módulo.
    """

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
