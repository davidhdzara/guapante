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

            # 2. Validación y Pesaje: "Recolectar" is still open, but user started weighing (quantity > 0 / picked = True)
            elif pick_pickings and any(p.state not in ['done', 'cancel'] for p in pick_pickings):
                active_picks = pick_pickings.filtered(lambda p: p.state not in ['done', 'cancel'])
                has_qty = False
                for p in active_picks:
                    if p.move_line_ids:
                        # In Odoo 18, `picked` indicates user action. If `picked` is not available, we assume true if quantity > 0 and state is in_progress
                        if any(getattr(ml, 'picked', False) for ml in p.move_line_ids):
                            has_qty = True
                            break
                        # Fallback for Odoo 17 or environments where picked isn't set but quantity is modified
                        elif not hasattr(p.move_line_ids, 'picked') and any(ml.quantity > 0 for ml in p.move_line_ids):
                            has_qty = True
                            break
                if has_qty:
                    status = 'preparing'
            
            order.guapante_delivery_status = status

    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        """Override to support fractional quantities (grams, packaging units).

        Odoo 18 truncates both add_qty and set_qty with int() in the standard
        _cart_update. This override detects fractional values, lets super()
        create/find the line with a ceiled integer, then corrects the quantity
        to the actual desired float value.
        """
        debug_msg = f"DEBUG KWARGS: {kwargs}\n"
        if self.note:
            self.note += debug_msg
        else:
            self.note = debug_msg
            
        float_add = float(add_qty or 0)
        float_set = float(set_qty or 0)

        is_fractional = (float_add and float_add != int(float_add)) or \
                        (float_set and float_set != int(float_set))

        if not is_fractional:
            return super()._cart_update(
                product_id, line_id=line_id,
                add_qty=add_qty, set_qty=set_qty, **kwargs
            )
            
        # Odoo native _cart_update converts no_variant_attribute_values (strings) 
        # to no_variant_attribute_value_ids (integers). We must do it BEFORE calling _cart_find_product_line.
        if 'no_variant_attribute_value_ids' not in kwargs and 'no_variant_attribute_values' in kwargs:
            product = self.env['product.product'].browse(product_id)
            no_var_vals = kwargs.get('no_variant_attribute_values') or []
            kwargs['no_variant_attribute_value_ids'] = product.env['product.template.attribute.value'].browse(
                [int(v) for v in no_var_vals]
            ).ids

        # Calculate the real desired quantity
        if float_set:
            desired_qty = float_set
        else:
            # Find existing line to add to its current qty
            if line_id:
                order_line = self._cart_find_product_line(product_id, line_id, **kwargs)[:1]
            else:
                # Guapante: search for the existing line using attributes native logic if line_id=None
                order_line = self._cart_find_product_line(product_id, None, **kwargs)[:1]
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
        
        # We must explicitly pass line_id=order_line.id if we found it, 
        # so super doesn't create duplications if its own internal matching fails!
        found_line_id = order_line.id if (not line_id and order_line) else line_id
        
        _logger.info("Guapante _cart_update: desired=%.4f, ceil=%d, passed_line_id=%s, su=%s",
                      desired_qty, ceil_qty, found_line_id, self.env.su)
        result = super()._cart_update(
            product_id, line_id=found_line_id,
            set_qty=ceil_qty, **kwargs
        )

        # Fix the actual quantity to the desired float value
        # .sudo() is required for public/anonymous users who lack
        # write access to sale.order.line
        if result and result.get('line_id'):
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

    def _cart_find_product_line(self, product_id, line_id=None, **kwargs):
        """
        Override to strengthen product line matching.
        Odoo 18 natively matches by exact order line name/description and exact list-order of attribute IDs.
        This leads to duplicate cart lines if the description slightly changed or attributes are received in a different order.
        Here we enforce matching primarily by product_id and exact set of attribute IDs, ignoring name differences.
        """
        self.ensure_one()
        
        # 1. Gather target attribute IDs that the user wants to add
        target_no_var_ids = set()
        if 'no_variant_attribute_value_ids' in kwargs:
            target_no_var_ids = set(kwargs['no_variant_attribute_value_ids'])
        elif 'no_variant_attribute_values' in kwargs:
            no_var_vals = kwargs.get('no_variant_attribute_values') or []
            target_no_var_ids = set(
                self.env['product.template.attribute.value'].browse([int(v) for v in no_var_vals]).ids
            )
            
        target_custom_vals = kwargs.get('product_custom_attribute_values') or []
        
        # 2. Iterate through existing cart lines and match based on strict rules (ignoring description text)
        lines = self.env['sale.order.line']
        for line in self.order_line:
            # Must be the same product variant
            if line.product_id.id != product_id:
                continue
                
            # If a specific line_id is requested, it must match
            if line_id and line.id != line_id:
                continue
                
            # Must match No-Variant Attributes exactly (ignoring list order by using sets)
            if hasattr(line, 'product_no_variant_attribute_value_ids'):
                line_no_var_ids = set(line.product_no_variant_attribute_value_ids.ids)
                if line_no_var_ids != target_no_var_ids:
                    continue
                
            # Must match Custom Attributes exactly (basic length validation)
            if hasattr(line, 'product_custom_attribute_value_ids'):
                line_custom_vals = line.product_custom_attribute_value_ids
                if len(target_custom_vals) != len(line_custom_vals):
                    continue
                
            # If we reach here, we found a perfect match based on product & attributes!
            lines |= line
            
        return lines

