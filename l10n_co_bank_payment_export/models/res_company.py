# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_co_dispersal_account = fields.Char(
        string='Cuenta Dispersora (Colombia)',
        size=20,
        help=(
            'Número de cuenta bancaria de la empresa desde la que se debitarán '
            'los pagos masivos. Requerido para Banco de Bogotá y Bancolombia. '
            'Se usarán solo los dígitos (máximo 11).'
        ),
    )
    l10n_co_dispersal_account_type = fields.Selection(
        selection=[
            ('S', 'Ahorros'),
            ('D', 'Corriente / Débito'),
            ('C', 'Contable'),
        ],
        string='Tipo Cuenta Dispersora',
        default='S',
        help=(
            'Tipo de la cuenta dispersora de la empresa. '
            'Bancolombia: S=Ahorros, D=Corriente/Débito, C=Contable. '
            'Banco de Bogotá: S→Ahorros(2), D→Corriente(1).'
        ),
    )
