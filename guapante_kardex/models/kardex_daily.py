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
        """
        today = fields.Date.context_today(self)
        # Todas las ubicaciones internas (compatible con multi-almacen)
        internal_locations = self.env['stock.location'].search([('usage', '=', 'internal')])
        if not internal_locations:
            return

        quants = self.env['stock.quant'].search([
            ('location_id', 'in', internal_locations.ids),
            ('quantity', '!=', 0)
        ])

        for quant in quants:
            # Crear snapshot del dia con el inventario actual
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
        Clasifica los movimientos:
          - Entrada (in): Proveedor/Produccion -> Interno
          - Venta (out): Interno -> Cliente
          - Desperdicio (scrap): Interno -> Desecho o Ajuste negativo de inventario
        """
        today = fields.Date.context_today(self)
        for move in moves.filtered(lambda m: m.state == 'done'):
            # Detectar si es entrada o salida de una ubicacion interna
            is_in = move.location_dest_id.usage == 'internal'
            is_out = move.location_id.usage == 'internal'
            
            if not (is_in or is_out):
                continue

            # Procesar entrada a ubicacion interna
            if is_in:
                self._update_kardex_line(today, move.product_id.id, move.location_dest_id.id, 'in', move.product_uom_qty)

            # Procesar salida de ubicacion interna
            if is_out:
                # Clasificar el tipo de salida
                dest = move.location_dest_id
                if dest.usage == 'customer':
                    # Es una venta real
                    direction = 'out'
                elif dest.scrap_location or dest.usage == 'inventory':
                    # Es un desperdicio o ajuste de inventario negativo
                    direction = 'scrap'
                else:
                    # Cualquier otra salida (transferencias entre bodegas, produccion, etc.)
                    direction = 'out'
                
                self._update_kardex_line(today, move.product_id.id, move.location_id.id, direction, move.product_uom_qty)

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
