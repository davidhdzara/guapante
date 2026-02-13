from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    guapante_delivery_status = fields.Selection([
        ('received', 'Recibido'),
        ('preparing', 'Preparando'),
        ('shipping', 'En Camino'),
        ('delivered', 'Entregado'),
    ], string="Estado de Entrega (Guapante)", compute='_compute_guapante_delivery_status')

    @api.depends('state', 'picking_ids.state')
    def _compute_guapante_delivery_status(self):
        for order in self:
            status = 'received' # Default: Order Confirmed
            
            # If order is not confirmed, it might be draft/sent, so we keep it simple or handle it.
            # Assuming this logic runs for confirmed orders primarily.
            
            pickings = order.picking_ids.filtered(lambda p: p.state != 'cancel')
            if pickings:
                # Logic:
                # If any picking is done -> En Camino (or delivered? User said stock output = En camino)
                # If any picking is assigned (Ready) -> Preparado
                # Else -> Recibido
                
                # Check for 'done' (Transferido)
                if any(p.state == 'done' for p in pickings):
                    status = 'shipping' 
                    # Note: 'Entregado' might need a manual trigger or a specific "delivered" date/pod.
                    # For now, let's stick to 'shipping' as per user requirement "En camino = salida de inventario"
                    # We can add logic for 'delivered' if proof of delivery is set, but user didn't specify.
                
                # Check for 'assigned' (Listo/Reservado)
                elif any(p.state == 'assigned' for p in pickings):
                    status = 'preparing'
            
            order.guapante_delivery_status = status
