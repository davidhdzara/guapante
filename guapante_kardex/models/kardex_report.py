from odoo import models, fields

class GuapanteKardexReport(models.TransientModel):
    _name = 'guapante.kardex.report'
    _description = 'Reporte Kardex Dinámico'

    product_id = fields.Many2one('product.product', string='Producto', required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unidad', related='product_id.uom_id')
    
    date_from = fields.Datetime(string='Fecha Inicio')
    date_to = fields.Datetime(string='Fecha Fin')

    # Valores
    initial_qty = fields.Float(string='Con cuánto inicié')
    in_qty = fields.Float(string='Cuánto se compró')
    out_qty = fields.Float(string='Cuánto se vendió')
    theoretical_qty = fields.Float(string='Total que debo tener', compute='_compute_totals', store=True)
    real_qty = fields.Float(string='Total en inventario')
    difference = fields.Float(string='Diferencia', compute='_compute_totals', store=True)

    def _compute_totals(self):
        for record in self:
            record.theoretical_qty = record.initial_qty + record.in_qty - record.out_qty
            record.difference = record.real_qty - record.theoretical_qty
