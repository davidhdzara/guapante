import math
import logging
from datetime import timedelta
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    daily_sequence = fields.Integer(
        string='# del día',
        default=0,
        copy=False,
        help='Consecutivo diario de la orden según la fecha de creación.',
    )

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if order.daily_sequence:
                continue
            order_date = order.date_order.date()
            count = self.env['sale.order'].search_count([
                ('state', 'in', ('sale', 'done')),
                ('date_order', '>=', fields.Datetime.to_datetime(order_date)),
                ('date_order', '<', fields.Datetime.to_datetime(order_date + timedelta(days=1))),
                ('id', '!=', order.id),
                ('daily_sequence', '>', 0),
            ])
            order.daily_sequence = count + 1
        return res

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
        ('preparing', 'Validación y Pesaje'),
        ('shipping', 'En Camino'),
        ('delivered', 'Entregado'),
    ], string="Estado de Entrega (Guapante)", compute='_compute_guapante_delivery_status', store=True)

    @api.depends('state', 'picking_ids.state', 'picking_ids.move_ids.quantity', 'picking_ids.move_line_ids.quantity')
    def _compute_guapante_delivery_status(self):
        for order in self:
            status = 'received' # Default: "Pedido Recibido"

            pickings = order.picking_ids.filtered(lambda p: p.state != 'cancel')
            if not pickings:
                order.guapante_delivery_status = status
                continue

            # Identify "Recolectar" (Internal/Pick) vs "Órdenes de entrega" (Outgoing/Out)
            pick_pickings = pickings.filtered(lambda p: p.picking_type_id.code == 'internal')
            out_pickings = pickings.filtered(lambda p: p.picking_type_id.code == 'outgoing')

            # Fallback for 1-step delivery: treat the outgoing as the primary picking step
            if not pick_pickings and out_pickings:
                pick_pickings = out_pickings

            # 4. Entregado: All outgoing deliveries are done
            if out_pickings and all(p.state == 'done' for p in out_pickings):
                status = 'delivered'

            # 3. En Camino: Delivery is assigned/in_progress OR picking is done (it entered the Delivery section)
            elif (out_pickings and any(p.state in ['assigned', 'in_progress'] for p in out_pickings)) or \
                 (pick_pickings and all(p.state == 'done' for p in pick_pickings) and out_pickings):
                status = 'shipping'

            # 2. Validación y Pesaje: "Recolectar" is still open, but user started weighing (quantity > 0)
            elif pick_pickings and any(p.state not in ['done', 'cancel'] for p in pick_pickings):
                active_picks = pick_pickings.filtered(lambda p: p.state not in ['done', 'cancel'])
                # Check if any quantity has been inputted (Odoo 18 uses quantity instead of quantity_done)
                has_qty = False
                for p in active_picks:
                    if p.move_line_ids:
                        if any(ml.quantity > 0 for ml in p.move_line_ids):
                            has_qty = True
                            break
                    elif p.move_ids:
                        if any(m.quantity > 0 for m in p.move_ids):
                            has_qty = True
                            break
                if has_qty:
                    status = 'preparing'
            
            # 1. Recibido is the default
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

