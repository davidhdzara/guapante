# -*- coding: utf-8 -*-
from odoo import fields, models

class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    is_b2b_exclusive = fields.Boolean(
        string='Exclusivo B2B',
        default=False,
        help='Si se marca, este empaque SOLO será visible en la tienda online para los clientes permitidos definidos abajo. Para el público general o clientes no listados, no existirá.'
    )

    b2b_exclusive_customer_ids = fields.Many2many(
        'res.partner',
        string='Clientes B2B Permitidos',
        domain=[('is_company', '=', True)],
        help='Lista de clientes (empresas) que pueden ver y comprar este empaque exclusivo en la tienda online.'
    )
