import math
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('order_line.product_uom_qty', 'order_line.product_id')
    def _compute_cart_info(self):
        """Override to use ceil() instead of int().

        Odoo 18 uses int(sum(qty)) for cart_quantity. For fractional
        quantities like 0.2 kg, int(0.2) = 0 which triggers
        cart_update_json → sale_reset() → deletes the entire order.
        Using ceil() ensures any non-zero quantity counts as at least 1.
        """
        for order in self:
            raw_qty = sum(order.mapped('website_order_line.product_uom_qty'))
            order.cart_quantity = math.ceil(raw_qty) if raw_qty > 0 else 0
            order.only_services = all(
                sol.product_id.type == 'service'
                for sol in order.website_order_line
            )

    guapante_delivery_status = fields.Selection([
        ('received', 'Recibido'),
        ('preparing', 'Preparando'),
        ('shipping', 'En Camino'),
        ('delivered', 'Entregado'),
    ], string="Estado de Entrega (Guapante)", compute='_compute_guapante_delivery_status', store=True)

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

    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        """Override to support fractional quantities (grams, packaging units).

        Odoo 18 truncates both add_qty and set_qty with int() in the standard
        _cart_update. This override detects fractional values, lets super()
        create/find the line with a ceiled integer, then corrects the quantity
        to the actual desired float value.
        """
        float_add = float(add_qty or 0)
        float_set = float(set_qty or 0)

        is_fractional = (float_add and float_add != int(float_add)) or \
                        (float_set and float_set != int(float_set))

        if not is_fractional:
            return super()._cart_update(
                product_id, line_id=line_id,
                add_qty=add_qty, set_qty=set_qty, **kwargs
            )

        # Calculate the real desired quantity
        if float_set:
            desired_qty = float_set
        else:
            # Find existing line to add to its current qty
            if line_id:
                order_line = self._cart_find_product_line(product_id, line_id, **kwargs)[:1]
            else:
                order_line = self.env['sale.order.line']
            current_qty = order_line.product_uom_qty if order_line else 0
            desired_qty = current_qty + float_add

        if desired_qty <= 0:
            # Deletion: let super handle it normally
            return super()._cart_update(
                product_id, line_id=line_id,
                add_qty=0, set_qty=0, **kwargs
            )

        # Call super with ceiled integer so the line gets created/found
        ceil_qty = max(1, math.ceil(desired_qty))
        _logger.info("Guapante _cart_update: desired=%.4f, ceil=%d, is_su=%s",
                      desired_qty, ceil_qty, self.env.su)
        result = super()._cart_update(
            product_id, line_id=line_id,
            set_qty=ceil_qty, **kwargs
        )

        # Fix the actual quantity to the desired float value
        # .sudo() is required for public/anonymous users who lack
        # write access to sale.order.line
        if result.get('line_id'):
            line = self.env['sale.order.line'].sudo().browse(result['line_id'])
            if line.exists() and line.product_uom_qty != desired_qty:
                line.product_uom_qty = desired_qty
                result['quantity'] = desired_qty
                _logger.info(
                    "Guapante _cart_update: fixed qty=%.4f on line %s (was %s)",
                    desired_qty, line.id, ceil_qty
                )
            else:
                _logger.info(
                    "Guapante _cart_update: line %s exists=%s, qty already=%.4f",
                    result.get('line_id'), line.exists(),
                    line.product_uom_qty if line.exists() else 0
                )

        return result

