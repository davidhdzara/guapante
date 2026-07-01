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
    
    qty_theoretical = fields.Float(string='Total que debo de tener', compute='_compute_totals', store=True)
    qty_real = fields.Float(string='Total en inventario', compute='_compute_totals', store=True)
    difference = fields.Float(string='Diferencia', compute='_compute_totals', store=True)

    _sql_constraints = [
        ('unique_daily_product_location', 'unique(date, product_id, location_id)', 'Solo puede haber un snapshot por producto, ubicación y fecha.')
    ]

    @api.depends('qty_start', 'qty_in', 'qty_out', 'date')
    def _compute_totals(self):
        for record in self:
            record.qty_theoretical = record.qty_start + record.qty_in - record.qty_out
            
            # Si es el registro de hoy, obtener el stock actual real
            if record.date == date.today():
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', record.product_id.id),
                    ('location_id', '=', record.location_id.id)
                ], limit=1)
                record.qty_real = quant.quantity if quant else 0.0
            else:
                # Si es un dia pasado, asumimos que el real quedo estatico en lo que diga el historial
                # Para simplificar y no hacer queries pesados al pasado, asumimos real = theoretical si no se actualizo
                # En un sistema real, un cron de fin de dia congelaria qty_real.
                record.qty_real = record.qty_theoretical
                
            record.difference = record.qty_real - record.qty_theoretical

    @api.model
    def take_daily_snapshot(self):
        """
        Cron job method. Se ejecuta a las 00:01 para crear el registro del nuevo dia
        basado en el stock real del quant en este instante.
        """
        today = date.today()
        # Solo ubicaciones internas principales
        wh_stock = self.env['stock.location'].search([('complete_name', '=', 'WH/Stock')], limit=1)
        if not wh_stock:
            return

        quants = self.env['stock.quant'].search([
            ('location_id', '=', wh_stock.id),
            ('quantity', '!=', 0)
        ])

        for quant in quants:
            # Crear snapshot del dia con el inventario actual
            existing = self.search([
                ('date', '=', today),
                ('product_id', '=', quant.product_id.id),
                ('location_id', '=', wh_stock.id)
            ])
            if not existing:
                self.create({
                    'date': today,
                    'product_id': quant.product_id.id,
                    'location_id': wh_stock.id,
                    'qty_start': quant.quantity,
                    'qty_in': 0.0,
                    'qty_out': 0.0,
                })

    @api.model
    def _sync_moves(self, moves):
        """
        Llamado desde stock.move _action_done para actualizar in/out del dia.
        """
        today = date.today()
        for move in moves.filtered(lambda m: m.state == 'done'):
            # Solo movimientos desde o hacia WH/Stock
            is_in = move.location_dest_id.complete_name == 'WH/Stock'
            is_out = move.location_id.complete_name == 'WH/Stock'
            
            if not (is_in or is_out):
                continue
                
            loc_id = move.location_dest_id.id if is_in else move.location_id.id
            
            # Buscar o crear el kardex del dia
            kardex = self.search([
                ('date', '=', today),
                ('product_id', '=', move.product_id.id),
                ('location_id', '=', loc_id)
            ], limit=1)
            
            if not kardex:
                # Obtener el stock real ANTES de este movimiento (aproximado)
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('location_id', '=', loc_id)
                ], limit=1)
                
                start_qty = quant.quantity if quant else 0.0
                if is_in:
                    start_qty -= move.product_uom_qty
                if is_out:
                    start_qty += move.product_uom_qty
                    
                kardex = self.create({
                    'date': today,
                    'product_id': move.product_id.id,
                    'location_id': loc_id,
                    'qty_start': start_qty,
                })
                
            # Sumar al kardex
            if is_in:
                kardex.qty_in += move.product_uom_qty
            if is_out:
                kardex.qty_out += move.product_uom_qty

