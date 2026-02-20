# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_seasonal = fields.Boolean(
        string='De Temporada',
        default=False,
        help='Marcar este producto para que aparezca en la sección "Cosecha en temporada" del home'
    )

    def write(self, vals):
        res = super().write(vals)
        if 'is_seasonal' in vals:
            self.env['ir.qweb'].clear_caches()
            self.env['website'].sudo().search([]).invalidate_recordset()
        return res
