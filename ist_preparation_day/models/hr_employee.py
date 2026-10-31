# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_guapante_prep_operator = fields.Boolean(
        string='Operario de Preparación (Guapante)',
        default=False,
        help=(
            'Habilita a este empleado para identificarse con su PIN como '
            'operario físico en Preparación del Día / Picking. Sin esto '
            'marcado, su PIN no identifica aunque esté configurado — '
            'evita que cualquier empleado con PIN pueda registrar pesos. '
            'Se gestiona desde Preparación > Configuración > Operarios '
            'autorizados — no aparece en la ficha del empleado (David, '
            '2026-10-29: ahí solo se ve el NIP).'
        ),
    )
