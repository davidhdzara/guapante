from odoo.tests.common import TransactionCase
from datetime import date

class TestKardexDaily(TransactionCase):

    def setUp(self):
        super(TestKardexDaily, self).setUp()
        self.product = self.env['product.product'].create({
            'name': 'Tomate Test',
            'type': 'product'
        })
        self.location_stock = self.env.ref('stock.stock_location_stock')
        self.location_customers = self.env.ref('stock.stock_location_customers')
        self.location_suppliers = self.env.ref('stock.stock_location_suppliers')

    def test_01_daily_snapshot_logic(self):
        """Prueba que el snapshot inicie en 0 y sume las entradas/salidas correctamente"""
        
        # 1. Simular inventario inicial forzado en stock.quant (100 unidades)
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'inventory_quantity': 100.0,
        })
        quant.action_apply_inventory()

        # 2. Correr el cron job para crear el snapshot de hoy
        self.env['guapante.kardex.daily'].take_daily_snapshot()

        # Verificar el Kardex de hoy
        kardex = self.env['guapante.kardex.daily'].search([
            ('product_id', '=', self.product.id),
            ('date', '=', date.today())
        ])
        self.assertTrue(kardex)
        self.assertEqual(kardex.qty_start, 100.0)
        self.assertEqual(kardex.qty_in, 0.0)
        self.assertEqual(kardex.qty_out, 0.0)
        self.assertEqual(kardex.qty_theoretical, 100.0)
        self.assertEqual(kardex.qty_real, 100.0)

        # 3. Crear una compra (Entrada de 20)
        move_in = self.env['stock.move'].create({
            'name': 'Compra Test',
            'product_id': self.product.id,
            'product_uom_qty': 20.0,
            'product_uom': self.product.uom_id.id,
            'location_id': self.location_suppliers.id,
            'location_dest_id': self.location_stock.id,
        })
        move_in._action_confirm()
        move_in.quantity = 20.0
        move_in._action_done()

        # Verificar Kardex despues de compra
        self.assertEqual(kardex.qty_in, 20.0)
        self.assertEqual(kardex.qty_theoretical, 120.0)
        self.assertEqual(kardex.qty_real, 120.0)

        # 4. Crear una venta (Salida de 5)
        move_out = self.env['stock.move'].create({
            'name': 'Venta Test',
            'product_id': self.product.id,
            'product_uom_qty': 5.0,
            'product_uom': self.product.uom_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customers.id,
        })
        move_out._action_confirm()
        move_out.quantity = 5.0
        move_out._action_done()

        # Verificar Kardex despues de venta
        self.assertEqual(kardex.qty_out, 5.0)
        self.assertEqual(kardex.qty_theoretical, 115.0)
        self.assertEqual(kardex.qty_real, 115.0)
        self.assertEqual(kardex.difference, 0.0)
