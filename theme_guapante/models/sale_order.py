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
                has_picked_field = 'picked' in self.env['stock.move.line']._fields
                has_qty = False
                for p in active_picks:
                    if p.move_line_ids:
                        # In Odoo 18, `picked` indicates user action.
                        if has_picked_field and any(ml.picked for ml in p.move_line_ids):
                            has_qty = True
                            break
                        # Fallback for Odoo 17 or environments where picked isn't set but quantity is modified
                        elif not has_picked_field and any(ml.quantity > 0 for ml in p.move_line_ids):
                            has_qty = True
                            break
                if has_qty:
                    status = 'preparing'
            
            order.guapante_delivery_status = status

    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        """Override to support fractional quantities (e.g. 500g = 0.5 kg).

        Odoo 18's native _cart_update truncates quantities with int(),
        so 0.5 kg becomes 0 and the line gets deleted. We ceil() to keep
        the line alive, then write the exact float value afterwards.
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

        # For fractional, find the existing line first
        existing_line = self._cart_find_product_line(product_id, line_id, **kwargs)[:1]

        if float_set:
            desired_qty = float_set
        else:
            current_qty = existing_line.product_uom_qty if existing_line else 0
            desired_qty = current_qty + float_add

        if desired_qty <= 0:
            return super()._cart_update(
                product_id, line_id=line_id, add_qty=0, set_qty=0, **kwargs
            )

        ceil_qty = max(1, math.ceil(desired_qty))
        found_line_id = existing_line.id if existing_line else line_id
        result = super()._cart_update(
            product_id, line_id=found_line_id, set_qty=ceil_qty, **kwargs
        )

        if result and result.get('line_id'):
            line = self.env['sale.order.line'].sudo().browse(result['line_id'])
            if line.exists() and line.product_uom_qty != desired_qty:
                line.product_uom_qty = desired_qty
                result['quantity'] = desired_qty
                _logger.info(
                    "Guapante _cart_update: wrote exact fractional qty=%.4f on line %s",
                    desired_qty, line.id
                )

        return result

    def _cart_find_product_line(self, product_id, line_id=None, **kwargs):
        """
        Override to fix attribute ID order sensitivity in Odoo 18 and
        ensure different packagings (Embalajes) of the same product do not merge.
        """
        self.ensure_one()

        # 1. Let Odoo's native logic run first
        lines = super()._cart_find_product_line(product_id, line_id, **kwargs)
        
        # 1.5. Guapante specific: DO NOT merge lines if they have different packagings.
        # This is critical for selling "Cilantro" in both 'g', 'kg', 'Paquete 200g', and 'Paquete 500g'
        # in the same cart as distinct lines.
        target_pkg_id = kwargs.get('product_packaging_id')
        if target_pkg_id:
            lines = lines.filtered(lambda l: l.product_packaging_id.id == int(target_pkg_id))
        else:
            # If no packaging requested, ONLY match lines that also have no packaging
            lines = lines.filtered(lambda l: not l.product_packaging_id)
            
        if lines:
            return lines

        # 2. Fallback: retry with set-based attribute comparison
        no_var_ids = kwargs.get('no_variant_attribute_value_ids') or []
        if not no_var_ids:
            return lines

        target_set = set(no_var_ids)
        matched = self.env['sale.order.line']
        for line in self.order_line:
            if line.product_id.id != product_id:
                continue
            if line_id and line.id != line_id:
                continue
                
            # Enforce packaging separation on the fallback too
            line_pkg_id = line.product_packaging_id.id if line.product_packaging_id else None
            req_pkg_id = int(target_pkg_id) if target_pkg_id else None
            if line_pkg_id != req_pkg_id:
                continue

            if hasattr(line, 'product_no_variant_attribute_value_ids'):
                if set(line.product_no_variant_attribute_value_ids.ids) == target_set:
                    matched |= line

        return matched


