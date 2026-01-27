# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_seasonal = fields.Boolean(
        string='De Temporada',
        default=False,
        help='Marcar este producto para que aparezca en la sección "Cosecha en temporada" del home'
    )
