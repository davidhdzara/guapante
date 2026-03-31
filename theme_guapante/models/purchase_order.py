# -*- coding: utf-8 -*-
from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    guapante_product_line_count = fields.Integer(
        string='Cantidad de Productos',
        compute='_compute_guapante_product_line_count',
    )

    @api.depends('order_line', 'order_line.display_type')
    def _compute_guapante_product_line_count(self):
        for order in self:
            order.guapante_product_line_count = len(
                order.order_line.filtered(lambda l: not l.display_type)
            )
