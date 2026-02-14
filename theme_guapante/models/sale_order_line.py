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
        store=True,
        readonly=False,
        compute='_compute_uom_mode',
        help='Unidad de medida en la que el cliente solicitó el producto en la tienda web.',
    )

    display_qty = fields.Char(
        string='Cantidad de Display',
        compute='_compute_display_qty',
        help='Cantidad formateada para mostrar en el frontend (ej: 900 g, 1.5 kg)',
    )

    display_uom_label = fields.Char(
        string='Etiqueta de UoM',
        compute='_compute_display_qty',
        help='Etiqueta de la unidad para el frontend (g, kg, Unidades)',
    )

    @api.depends('product_id', 'product_id.uom_id', 'product_id.uom_id.category_id')
    def _compute_uom_mode(self):
        """Default: weight products → 'kg', otherwise → 'unit'.
        This can be overwritten by the cart controller when user picks 'g'.
        """
        weight_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        for line in self:
            if weight_categ and line.product_id.uom_id.category_id == weight_categ:
                line.uom_mode = 'kg'
            else:
                line.uom_mode = 'unit'

    @api.depends('product_uom_qty', 'uom_mode', 'product_uom')
    def _compute_display_qty(self):
        """Compute the display quantity and label based on the user's chosen mode."""
        for line in self:
            mode = line.uom_mode or 'unit'

            if mode == 'g':
                # Backend stores kg → display as grams
                grams = round(line.product_uom_qty * 1000)
                line.display_qty = str(int(grams))
                line.display_uom_label = 'g'
            elif mode == 'kg':
                # Show with up to 2 decimals, strip trailing zeros
                val = round(line.product_uom_qty, 2)
                if val == int(val):
                    line.display_qty = str(int(val))
                else:
                    line.display_qty = str(val)
                line.display_uom_label = 'kg'
            else:
                # Units — always integer
                line.display_qty = str(int(line.product_uom_qty))
                line.display_uom_label = line.product_uom.name or 'Unidades'
