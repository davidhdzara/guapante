from odoo import models, fields, api
from datetime import datetime

class KardexWizard(models.TransientModel):
    _name = 'guapante.kardex.wizard'
    _description = 'Asistente de Kardex'

    date_from = fields.Datetime(string='Fecha Inicio', required=True, default=fields.Datetime.now)
    date_to = fields.Datetime(string='Fecha Fin', required=True, default=fields.Datetime.now)
    location_id = fields.Many2one('stock.location', string='Ubicación', domain="[('usage', '=', 'internal')]", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super(KardexWizard, self).default_get(fields_list)
        wh_stock = self.env['stock.location'].search([('complete_name', '=', 'WH/Stock')], limit=1)
        if wh_stock:
            res['location_id'] = wh_stock.id
        return res

    def generate_kardex(self):
        # Limpiar tabla temporal
        self.env['guapante.kardex.report'].search([]).unlink()
        
        loc_id = self.location_id.id
        date_from = self.date_from
        date_to = self.date_to

        # Productos que han tenido movimiento o tienen stock
        self.env.cr.execute("""
            SELECT DISTINCT product_id 
            FROM stock_move_line 
            WHERE (location_id = %s OR location_dest_id = %s)
               AND state = 'done'
        """, (loc_id, loc_id))
        
        product_ids = [row[0] for row in self.env.cr.fetchall()]
        
        # Tambien agregar productos que tienen inventario actual aunque no tengan movimientos en esta vista
        quants = self.env['stock.quant'].search([('location_id', '=', loc_id), ('quantity', '!=', 0)])
        product_ids = list(set(product_ids + quants.mapped('product_id.id')))
        
        report_data = []
        for p_id in product_ids:
            # Saldo Inicial: Todas las entradas antes de date_from MENOS todas las salidas antes de date_from
            self.env.cr.execute("""
                SELECT sum(qty_done) FROM stock_move_line 
                WHERE product_id = %s AND location_dest_id = %s AND state = 'done' AND date < %s
            """, (p_id, loc_id, date_from))
            in_before = self.env.cr.fetchone()[0] or 0.0

            self.env.cr.execute("""
                SELECT sum(qty_done) FROM stock_move_line 
                WHERE product_id = %s AND location_id = %s AND state = 'done' AND date < %s
            """, (p_id, loc_id, date_from))
            out_before = self.env.cr.fetchone()[0] or 0.0
            
            initial_qty = in_before - out_before

            # Movimientos en el periodo
            self.env.cr.execute("""
                SELECT sum(qty_done) FROM stock_move_line 
                WHERE product_id = %s AND location_dest_id = %s AND state = 'done' AND date >= %s AND date <= %s
            """, (p_id, loc_id, date_from, date_to))
            in_period = self.env.cr.fetchone()[0] or 0.0

            self.env.cr.execute("""
                SELECT sum(qty_done) FROM stock_move_line 
                WHERE product_id = %s AND location_id = %s AND state = 'done' AND date >= %s AND date <= %s
            """, (p_id, loc_id, date_from, date_to))
            out_period = self.env.cr.fetchone()[0] or 0.0
            
            # Stock Real Actual
            quant = self.env['stock.quant'].search([('product_id', '=', p_id), ('location_id', '=', loc_id)], limit=1)
            real_qty = quant.quantity if quant else 0.0
            
            # Si todo esta en 0, no lo mostramos
            if initial_qty == 0 and in_period == 0 and out_period == 0 and real_qty == 0:
                continue

            report_data.append({
                'product_id': p_id,
                'date_from': date_from,
                'date_to': date_to,
                'initial_qty': initial_qty,
                'in_qty': in_period,
                'out_qty': out_period,
                'real_qty': real_qty,
            })
            
        if report_data:
            self.env['guapante.kardex.report'].create(report_data)

        # Retornar vista
        return {
            'name': 'Reporte Kardex',
            'type': 'ir.actions.act_window',
            'res_model': 'guapante.kardex.report',
            'view_mode': 'pivot,tree',
            'target': 'current',
        }
