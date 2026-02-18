# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestModuleInstall(TransactionCase):
    """Basic installation and field-existence tests for theme_guapante."""

    def test_module_installed(self):
        """theme_guapante should be in the list of installed modules."""
        module = self.env['ir.module.module'].search([
            ('name', '=', 'theme_guapante'),
            ('state', '=', 'installed'),
        ])
        self.assertTrue(module, "theme_guapante module should be installed")

    def test_product_template_is_seasonal_field(self):
        """product.template should have the is_seasonal Boolean field."""
        field = self.env['ir.model.fields'].search([
            ('model', '=', 'product.template'),
            ('name', '=', 'is_seasonal'),
        ])
        self.assertTrue(field, "Field 'is_seasonal' should exist on product.template")
        self.assertEqual(field.ttype, 'boolean')

    def test_sale_order_delivery_status_field(self):
        """sale.order should have the guapante_delivery_status Selection field."""
        field = self.env['ir.model.fields'].search([
            ('model', '=', 'sale.order'),
            ('name', '=', 'guapante_delivery_status'),
        ])
        self.assertTrue(field, "Field 'guapante_delivery_status' should exist on sale.order")
        self.assertEqual(field.ttype, 'selection')

    def test_sale_order_line_uom_mode_field(self):
        """sale.order.line should have the uom_mode Selection field."""
        field = self.env['ir.model.fields'].search([
            ('model', '=', 'sale.order.line'),
            ('name', '=', 'uom_mode'),
        ])
        self.assertTrue(field, "Field 'uom_mode' should exist on sale.order.line")
        self.assertEqual(field.ttype, 'selection')

    def test_stock_picking_vehicle_fields(self):
        """stock.picking should have vehicle_id and driver_id Many2one fields."""
        vehicle_field = self.env['ir.model.fields'].search([
            ('model', '=', 'stock.picking'),
            ('name', '=', 'vehicle_id'),
        ])
        driver_field = self.env['ir.model.fields'].search([
            ('model', '=', 'stock.picking'),
            ('name', '=', 'driver_id'),
        ])
        self.assertTrue(vehicle_field, "Field 'vehicle_id' should exist on stock.picking")
        self.assertTrue(driver_field, "Field 'driver_id' should exist on stock.picking")
        self.assertEqual(vehicle_field.ttype, 'many2one')
        self.assertEqual(driver_field.ttype, 'many2one')
