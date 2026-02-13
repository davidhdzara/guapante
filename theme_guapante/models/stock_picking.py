from odoo import models, fields, api

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehículo Asignado")
    driver_id = fields.Many2one('res.partner', string="Conductor")
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Auto-asignar conductor basado en el vehículo"""
        if self.vehicle_id and self.vehicle_id.driver_id:
            self.driver_id = self.vehicle_id.driver_id
