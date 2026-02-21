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
            # Invalidate only the affected product records so the website
            # picks up the new is_seasonal value without nuking the entire
            # ORM registry cache (which would cause performance spikes).
            self.invalidate_recordset(['is_seasonal'])
        return res
