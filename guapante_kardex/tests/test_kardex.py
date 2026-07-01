from odoo.tests.common import TransactionCase
from datetime import date

class TestKardexDaily(TransactionCase):

    def setUp(self):
        super(TestKardexDaily, self).setUp()
        self.product = self.env['product.product'].create({
            'name': 'Tomate Test',
            'is_storable': True,
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
        self.assertTrue(kardex, "El snapshot debio haberse creado")
        self.assertEqual(kardex.qty_start, 100.0, "Saldo inicial debe ser 100")
        self.assertEqual(kardex.qty_in, 0.0)
        self.assertEqual(kardex.qty_out, 0.0)
        self.assertEqual(kardex.qty_scrap, 0.0)
        self.assertEqual(kardex.qty_theoretical, 100.0)

    def test_02_compra_actualiza_kardex(self):
        """Prueba que una compra actualice qty_in correctamente"""
        # Preparar inventario inicial
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'inventory_quantity': 50.0,
        })
        quant.action_apply_inventory()
        self.env['guapante.kardex.daily'].take_daily_snapshot()

        # Crear una compra (Entrada de 20)
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

        kardex = self.env['guapante.kardex.daily'].search([
            ('product_id', '=', self.product.id),
            ('date', '=', date.today())
        ])
        self.assertEqual(kardex.qty_in, 20.0, "Compra de 20 debe reflejarse")
        self.assertEqual(kardex.qty_theoretical, 70.0, "50 + 20 = 70")

    def test_03_venta_actualiza_kardex(self):
        """Prueba que una venta actualice qty_out correctamente"""
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'inventory_quantity': 80.0,
        })
        quant.action_apply_inventory()
        self.env['guapante.kardex.daily'].take_daily_snapshot()

        # Crear una venta (Salida de 15 a cliente)
        move_out = self.env['stock.move'].create({
            'name': 'Venta Test',
            'product_id': self.product.id,
            'product_uom_qty': 15.0,
            'product_uom': self.product.uom_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customers.id,
        })
        move_out._action_confirm()
        move_out.quantity = 15.0
        move_out._action_done()

        kardex = self.env['guapante.kardex.daily'].search([
            ('product_id', '=', self.product.id),
            ('date', '=', date.today())
        ])
        self.assertEqual(kardex.qty_out, 15.0, "Venta de 15 debe reflejarse")
        self.assertEqual(kardex.qty_theoretical, 65.0, "80 - 15 = 65")

    def test_04_desperdicio_se_separa_de_ventas(self):
        """Prueba que un desperdicio NO sume a ventas sino a la columna Desperdicios"""
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'inventory_quantity': 100.0,
        })
        quant.action_apply_inventory()
        self.env['guapante.kardex.daily'].take_daily_snapshot()

        # Buscar o crear ubicacion de scrap
        scrap_loc = self.env['stock.location'].search([('scrap_location', '=', True)], limit=1)

        # Crear un movimiento de desperdicio (Scrap de 3)
        move_scrap = self.env['stock.move'].create({
            'name': 'Desperdicio Test',
            'product_id': self.product.id,
            'product_uom_qty': 3.0,
            'product_uom': self.product.uom_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': scrap_loc.id,
        })
        move_scrap._action_confirm()
        move_scrap.quantity = 3.0
        move_scrap._action_done()

        kardex = self.env['guapante.kardex.daily'].search([
            ('product_id', '=', self.product.id),
            ('date', '=', date.today())
        ])
        self.assertEqual(kardex.qty_out, 0.0, "La venta debe estar en 0 (no fue una venta)")
        self.assertEqual(kardex.qty_scrap, 3.0, "El desperdicio debe ser 3")
        self.assertEqual(kardex.qty_theoretical, 97.0, "100 - 0 - 3 = 97")

    def test_05_formula_completa(self):
        """Prueba la formula: Teorico = Inicio + Compras - Ventas - Desperdicios"""
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'inventory_quantity': 200.0,
        })
        quant.action_apply_inventory()
        self.env['guapante.kardex.daily'].take_daily_snapshot()

        scrap_loc = self.env['stock.location'].search([('scrap_location', '=', True)], limit=1)

        # Compra de 50
        move_in = self.env['stock.move'].create({
            'name': 'Compra', 'product_id': self.product.id,
            'product_uom_qty': 50.0, 'product_uom': self.product.uom_id.id,
            'location_id': self.location_suppliers.id,
            'location_dest_id': self.location_stock.id,
        })
        move_in._action_confirm()
        move_in.quantity = 50.0
        move_in._action_done()

        # Venta de 30
        move_out = self.env['stock.move'].create({
            'name': 'Venta', 'product_id': self.product.id,
            'product_uom_qty': 30.0, 'product_uom': self.product.uom_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customers.id,
        })
        move_out._action_confirm()
        move_out.quantity = 30.0
        move_out._action_done()

        # Desperdicio de 10
        move_scrap = self.env['stock.move'].create({
            'name': 'Scrap', 'product_id': self.product.id,
            'product_uom_qty': 10.0, 'product_uom': self.product.uom_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': scrap_loc.id,
        })
        move_scrap._action_confirm()
        move_scrap.quantity = 10.0
        move_scrap._action_done()

        kardex = self.env['guapante.kardex.daily'].search([
            ('product_id', '=', self.product.id),
            ('date', '=', date.today())
        ])
        # 200 + 50 - 30 - 10 = 210
        self.assertEqual(kardex.qty_start, 200.0)
        self.assertEqual(kardex.qty_in, 50.0)
        self.assertEqual(kardex.qty_out, 30.0)
        self.assertEqual(kardex.qty_scrap, 10.0)
        self.assertEqual(kardex.qty_theoretical, 210.0, "200 + 50 - 30 - 10 = 210")
