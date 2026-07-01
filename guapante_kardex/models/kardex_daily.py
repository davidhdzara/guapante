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
        Excluye WH/Entrada y WH/Salida que son zonas de transito y causan doble conteo.
        """
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        if not warehouse:
            return self.env['stock.location']
        
        # lot_stock_id es la ubicacion principal del almacen (WH/Stock)
        main_stock = warehouse.lot_stock_id
        if not main_stock:
            return self.env['stock.location']
        
        # Buscar WH/Stock y todas sus sub-ubicaciones (Cava, General, Oficina)
        tracked = self.env['stock.location'].search([
            ('id', 'child_of', main_stock.id),
            ('usage', '=', 'internal'),
        ])
        return tracked

    @api.depends('qty_start', 'qty_in', 'qty_out', 'qty_scrap', 'date')
    def _compute_totals(self):
        for record in self:
            record.qty_theoretical = record.qty_start + record.qty_in - record.qty_out - record.qty_scrap
            
            # Si es el registro de hoy, obtener el stock actual real
            if record.date == fields.Date.context_today(self):
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', record.product_id.id),
                    ('location_id', '=', record.location_id.id)
                ], limit=1)
                record.qty_real = quant.quantity if quant else 0.0
            else:
                # Para dias pasados, el stock real ya fue congelado por el cron de cierre
                record.qty_real = record.qty_theoretical
                
            record.difference = record.qty_real - record.qty_theoretical

    @api.model
    def take_daily_snapshot(self):
        """
        Cron job method. Se ejecuta a las 00:01 para crear el registro del nuevo dia
        basado en el stock real del quant en este instante.
        Solo rastrea ubicaciones de almacenamiento principal (WH/Stock y sub-ubicaciones).
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
        Llamado desde stock.move _action_done para actualizar in/out/scrap del dia.
        
        SOLO rastrea movimientos que entran o salen de WH/Stock (y sub-ubicaciones).
        Ignora movimientos entre zonas de transito (WH/Entrada, WH/Salida).
        
        Clasificacion:
          - Compra (in): Algo entra a WH/Stock desde FUERA de WH/Stock
          - Venta (out): Algo sale de WH/Stock hacia clientes
          - Desperdicio (scrap): Algo sale de WH/Stock hacia desecho/ajuste inventario
          - Interno (ignorado): Movimientos dentro de WH/Stock (ej: Stock -> Stock/Cava)
        """
        today = fields.Date.context_today(self)
        tracked_locations = self._get_tracked_locations()
        tracked_ids = set(tracked_locations.ids)
        
        for move in moves.filtered(lambda m: m.state == 'done'):
            src_tracked = move.location_id.id in tracked_ids
            dest_tracked = move.location_dest_id.id in tracked_ids
            
            # Caso 1: Movimiento interno entre ubicaciones rastreadas (ej: Stock -> Stock/Cava)
            # IGNORAR - no es ni compra ni venta
            if src_tracked and dest_tracked:
                continue
            
            # Caso 2: Algo ENTRA a una ubicacion rastreada desde afuera
            # = COMPRA (sin importar si viene de proveedor, WH/Entrada, produccion, etc.)
            if dest_tracked and not src_tracked:
                self._update_kardex_line(
                    today, move.product_id.id, move.location_dest_id.id, 
                    'in', move.product_uom_qty
                )
            
            # Caso 3: Algo SALE de una ubicacion rastreada hacia afuera
            if src_tracked and not dest_tracked:
                dest = move.location_dest_id
                if dest.usage == 'customer':
                    direction = 'out'
                elif dest.scrap_location or dest.usage == 'inventory':
                    direction = 'scrap'
                else:
                    # Salida hacia WH/Salida u otra zona de transito = es una venta en proceso
                    direction = 'out'
                
                self._update_kardex_line(
                    today, move.product_id.id, move.location_id.id, 
                    direction, move.product_uom_qty
                )

    def _update_kardex_line(self, today, product_id, location_id, direction, qty):
        """
        Actualiza o crea la linea del kardex de forma atomica (evita race conditions).
        direction: 'in', 'out', o 'scrap'
        """
        kardex = self.search([
            ('date', '=', today),
            ('product_id', '=', product_id),
            ('location_id', '=', location_id)
        ], limit=1)

        if not kardex:
            # Obtener el stock real ANTES de este movimiento (aproximado)
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

        # Actualizar de forma atomica con SQL para evitar race conditions
        field_map = {'in': 'qty_in', 'out': 'qty_out', 'scrap': 'qty_scrap'}
        field_name = field_map[direction]
        self.env.cr.execute(
            f"UPDATE guapante_kardex_daily SET {field_name} = {field_name} + %s WHERE id = %s",
            (qty, kardex.id)
        )
        kardex.invalidate_recordset([field_name])
