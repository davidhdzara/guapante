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
        default='unit',
        help='Modo de unidad de medida seleccionado por el usuario (ej. Gramos vs Kg).',
    )



    # DEPRECATED: Kept temporarily to prevent crashes with stale views
    display_qty = fields.Char(compute='_compute_legacy_display')
    display_uom_label = fields.Char(compute='_compute_legacy_display')

    def _compute_legacy_display(self):
        for line in self:
            line.display_qty = str(line.product_uom_qty)
            line.display_uom_label = line.product_uom.name or ''
