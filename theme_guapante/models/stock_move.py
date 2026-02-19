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

    @api.depends('sale_line_id', 'sale_line_id.uom_mode', 'sale_line_id.product_uom_qty')
    def _compute_customer_uom_display(self):
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)

        for move in self:
            line = move.sale_line_id
            if not line:
                move.customer_qty_display = ''
                move.customer_uom_display = ''
                continue

            mode = line.uom_mode or 'unit'
            qty = line.product_uom_qty

            if mode == 'g':
                move.customer_qty_display = str(int(round(qty * 1000)))
                move.customer_uom_display = 'g'

            elif mode == 'kg':
                val = round(qty, 2)
                move.customer_qty_display = str(int(val)) if val == int(val) else str(val)
                move.customer_uom_display = 'kg'

            else:
                # Unit mode: convert kg → units via sales packaging
                is_weight = weight_categ and line.product_id.uom_id.category_id == weight_categ
                if is_weight:
                    packaging = line.product_id.packaging_ids.filtered(
                        lambda p: p.sales and p.qty > 0
                    )[:1]
                    if packaging:
                        qty_units = round(qty / packaging.qty)
                    else:
                        qty_units = int(qty) if qty == int(qty) else qty
                else:
                    qty_units = int(qty) if qty == int(qty) else qty

                move.customer_qty_display = str(int(qty_units))
                move.customer_uom_display = 'Unidades'
