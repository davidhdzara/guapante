from odoo import models, fields, api
from datetime import date

class GuapanteKardexDaily(models.Model):
    _name = 'guapante.kardex.daily'
    _description = 'Kardex Diario (Snapshot)'
    _order = 'date desc, product_id'

    date = fields.Date(string='Fecha', required=True, index=True, default=fields.Date.context_today)
    product_id = fields.Many2one('product.product', string='Producto', required=True, index=True)
    location_id = fields.Many2one('stock.location', string='Ubicación', required=True, index=True)
    
    qty_start = fields.Float(string='Con cuanto inicie', required=True, default=0.0)
    qty_in = fields.Float(string='Cuanto se compro', default=0.0)
    qty_out = fields.Float(string='Cuanto se vendio', default=0.0)
    qty_scrap = fields.Float(string='Desperdicios', default=0.0)
    
    qty_theoretical = fields.Float(string='Total que debo de tener', compute='_compute_totals', store=True)
    qty_real = fields.Float(string='Total en inventario', compute='_compute_totals', store=True)
    difference = fields.Float(string='Diferencia', compute='_compute_totals', store=True)

    _sql_constraints = [
        ('unique_daily_product_location', 'unique(date, product_id, location_id)', 'Solo puede haber un snapshot por producto, ubicación y fecha.')
    ]

    @api.model
    def _get_tracked_locations(self):
        """
        Retorna SOLO las ubicaciones de almacenamiento principal (WH/Stock y sus hijos).
        Excluye WH/Entrada y WH/Salida que son zonas de transito.
        """
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        if not warehouse:
            return self.env['stock.location']
        main_stock = warehouse.lot_stock_id
        if not main_stock:
            return self.env['stock.location']
        return self.env['stock.location'].search([
            ('id', 'child_of', main_stock.id),
            ('usage', '=', 'internal'),
        ])

    @api.depends('qty_start', 'qty_in', 'qty_out', 'qty_scrap', 'date')
    def _compute_totals(self):
        for record in self:
            record.qty_theoretical = record.qty_start + record.qty_in - record.qty_out - record.qty_scrap
            
            if record.date == fields.Date.context_today(self):
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', record.product_id.id),
                    ('location_id', '=', record.location_id.id)
                ], limit=1)
                record.qty_real = quant.quantity if quant else 0.0
            else:
                record.qty_real = record.qty_theoretical
                
            record.difference = record.qty_real - record.qty_theoretical

    @api.model
    def take_daily_snapshot(self):
        """
        Cron job. Se ejecuta a las 00:01 para crear el registro del nuevo dia.
        Solo rastrea WH/Stock y sub-ubicaciones.
        """
        today = fields.Date.context_today(self)
        tracked_locations = self._get_tracked_locations()
        if not tracked_locations:
            return

        quants = self.env['stock.quant'].search([
            ('location_id', 'in', tracked_locations.ids),
            ('quantity', '!=', 0)
        ])

        for quant in quants:
            existing = self.search([
                ('date', '=', today),
                ('product_id', '=', quant.product_id.id),
                ('location_id', '=', quant.location_id.id)
            ])
            if not existing:
                self.create({
                    'date': today,
                    'product_id': quant.product_id.id,
                    'location_id': quant.location_id.id,
                    'qty_start': quant.quantity,
                    'qty_in': 0.0,
                    'qty_out': 0.0,
                    'qty_scrap': 0.0,
                })

    @api.model
    def _sync_moves(self, moves):
        """
        Llamado desde stock.move._action_done().
        
        Clasificacion precisa de movimientos:
          - COMPRA: Entra a WH/Stock desde zona de recepcion (WH/Entrada) o proveedor directo
          - VENTA: Sale de WH/Stock hacia zona de despacho (WH/Salida) o cliente directo
          - DESPERDICIO: Sale de WH/Stock hacia ubicacion de desecho (scrap_location=True)
          - AJUSTE: Entra/sale desde Virtual Locations/Inventory adjustment -> modifica qty_start
          
        Movimientos internos entre ubicaciones rastreadas (ej: Stock->Stock/Cava) se IGNORAN.
        """
        today = fields.Date.context_today(self)
        tracked_locations = self._get_tracked_locations()
        tracked_ids = set(tracked_locations.ids)
        
        for move in moves.filtered(lambda m: m.state == 'done'):
            src_tracked = move.location_id.id in tracked_ids
            dest_tracked = move.location_dest_id.id in tracked_ids
            
            # Ignorar movimientos internos entre ubicaciones rastreadas
            if src_tracked and dest_tracked:
                continue
            
            # === ENTRADA a ubicacion rastreada ===
            if dest_tracked and not src_tracked:
                src = move.location_id
                
                if src.usage == 'inventory':
                    # Ajuste de inventario positivo -> modifica saldo inicial, NO es compra
                    self._adjust_start_balance(today, move.product_id.id, move.location_dest_id.id, move.product_uom_qty)
                else:
                    # Compra real (desde proveedor, WH/Entrada, produccion, etc.)
                    self._update_kardex_line(today, move.product_id.id, move.location_dest_id.id, 'in', move.product_uom_qty)
            
            # === SALIDA de ubicacion rastreada ===
            if src_tracked and not dest_tracked:
                dest = move.location_dest_id
                
                if dest.usage == 'inventory':
                    # Ajuste de inventario negativo -> modifica saldo inicial, NO es desperdicio
                    self._adjust_start_balance(today, move.product_id.id, move.location_id.id, -move.product_uom_qty)
                elif dest.scrap_location:
                    # Desperdicio real (ubicacion de desecho)
                    self._update_kardex_line(today, move.product_id.id, move.location_id.id, 'scrap', move.product_uom_qty)
                else:
                    # Venta (hacia WH/Salida, cliente directo, etc.)
                    self._update_kardex_line(today, move.product_id.id, move.location_id.id, 'out', move.product_uom_qty)

    def _adjust_start_balance(self, today, product_id, location_id, qty_delta):
        """
        Ajusta el saldo inicial del dia (para ajustes de inventario).
        Si el ajuste es positivo, sube qty_start. Si es negativo, lo baja.
        """
        kardex = self.search([
            ('date', '=', today),
            ('product_id', '=', product_id),
            ('location_id', '=', location_id)
        ], limit=1)

        if not kardex:
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product_id),
                ('location_id', '=', location_id)
            ], limit=1)
            start_qty = quant.quantity if quant else 0.0
            # Descontar el ajuste actual para obtener el inicio real
            start_qty -= qty_delta

            kardex = self.create({
                'date': today,
                'product_id': product_id,
                'location_id': location_id,
                'qty_start': start_qty,
            })
        
        # Actualizar saldo inicial de forma atomica
        self.env.cr.execute(
            "UPDATE guapante_kardex_daily SET qty_start = qty_start + %s WHERE id = %s",
            (qty_delta, kardex.id)
        )
        kardex.invalidate_recordset(['qty_start'])

    def _update_kardex_line(self, today, product_id, location_id, direction, qty):
        """
        Actualiza o crea la linea del kardex de forma atomica.
        direction: 'in' (compra), 'out' (venta), o 'scrap' (desperdicio)
        """
        kardex = self.search([
            ('date', '=', today),
            ('product_id', '=', product_id),
            ('location_id', '=', location_id)
        ], limit=1)

        if not kardex:
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product_id),
                ('location_id', '=', location_id)
            ], limit=1)

            start_qty = quant.quantity if quant else 0.0
            if direction == 'in':
                start_qty -= qty
            else:
                start_qty += qty

            kardex = self.create({
                'date': today,
                'product_id': product_id,
                'location_id': location_id,
                'qty_start': start_qty,
            })

        field_map = {'in': 'qty_in', 'out': 'qty_out', 'scrap': 'qty_scrap'}
        field_name = field_map[direction]
        self.env.cr.execute(
            f"UPDATE guapante_kardex_daily SET {field_name} = {field_name} + %s WHERE id = %s",
            (qty, kardex.id)
        )
        kardex.invalidate_recordset([field_name])
