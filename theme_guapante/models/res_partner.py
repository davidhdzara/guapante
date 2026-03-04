# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    guapante_order_zone = fields.Selection([
        ('cocina', 'Cocina'),
        ('bar', 'Bar'),
        ('personal', 'Personal'),
        ('evento', 'Evento')
    ], string='Zona de la orden', help='Zona a la que va dirigido el pedido dentro de la dirección.')
