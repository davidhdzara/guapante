# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_guapante_prep_operator = fields.Boolean(
        string='Operario de Preparación (Guapante)',
        default=False,
        help='Habilita a este empleado para identificarse con su PIN como operario físico en Preparación del Día / Picking.',
    )
