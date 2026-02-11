# -*- coding: utf-8 -*-
from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    uom_mode = fields.Selection(
        selection=[
            ('unit', 'Unidades'),
            ('kg', 'Kilogramos'),
            ('g', 'Gramos'),
        ],
        string='Modo de UoM del Cliente',
        compute='_compute_uom_mode',
        help='Modo de unidad de medida detectado desde el producto',
    )

    @api.depends('product_id', 'product_id.uom_id', 'product_id.uom_id.category_id')
    def _compute_uom_mode(self):
        """Detect UoM mode dynamically from the product's UoM category.
        Weight products (kg category) → 'kg', otherwise → 'unit'.
        No stored field needed, avoids DB column requirement.
        """
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        for line in self:
            if weight_categ and line.product_id.uom_id.category_id == weight_categ:
                line.uom_mode = 'kg'
            else:
                line.uom_mode = 'unit'
