# -*- coding: utf-8 -*-
from odoo import fields, models, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    customer_qty_display = fields.Char(
        string='Cant. Cliente',
        compute='_compute_customer_uom_display',
        store=False,
    )
    customer_uom_display = fields.Char(
        string='UdM Cliente',
        compute='_compute_customer_uom_display',
        store=False,
    )

    @api.depends('sale_line_id', 'purchase_line_id')
    def _compute_customer_uom_display(self):
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)

        for move in self:
            s_line = move.sale_line_id
            p_line = move.purchase_line_id if hasattr(move, 'purchase_line_id') else False
            
            if s_line:
                mode = s_line.uom_mode or 'unit'
                qty = s_line.product_uom_qty
                pack_filter = lambda p: p.sales and p.qty > 0
                product = s_line.product_id
            elif p_line:
                mode = p_line.uom_mode or 'unit'
                qty = p_line.product_qty
                pack_filter = lambda p: p.purchase and p.qty > 0
                product = p_line.product_id
            else:
                move.customer_qty_display = ''
                move.customer_uom_display = ''
                continue

            if mode == 'g':
                move.customer_qty_display = str(int(round(qty * 1000)))
                move.customer_uom_display = 'g'
            elif mode == 'kg':
                val = round(qty, 2)
                move.customer_qty_display = str(int(val)) if val == int(val) else str(val)
                move.customer_uom_display = 'kg'
            else:
                is_weight = weight_categ and product.uom_id.category_id == weight_categ
                if is_weight:
                    packaging = product.packaging_ids.filtered(pack_filter)[:1]
                    if packaging:
                        qty_units = round(qty / packaging.qty)
                    else:
                        qty_units = int(qty) if qty == int(qty) else qty
                else:
                    qty_units = int(qty) if qty == int(qty) else qty

                move.customer_qty_display = str(int(qty_units))
                move.customer_uom_display = 'Unidades'

    @api.onchange('quantity')
    def _onchange_quantity_tolerance(self):
        """ Alerta suave si el operario digita más del 20% del peso esperado """
        for move in self:
            if move.product_uom_qty > 0 and move.quantity > 0:
                expected_kg = move.product_uom_qty
                registered_kg = move.quantity
                
                # Revisa si es un producto por peso
                weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
                if not weight_categ or move.product_id.uom_id.category_id != weight_categ:
                    continue
                    
                if registered_kg > (expected_kg * 1.20):
                    return {
                        'warning': {
                            'title': '⚠️ Alerta de Tolerancia de Peso',
                            'message': f'La cantidad pesada ({registered_kg} kg) excede en más de un 20% lo pedido ({expected_kg} kg). Asegúrate de que la báscula y el producto sean correctos.'
                        }
                    }
