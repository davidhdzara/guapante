# -*- coding: utf-8 -*-
"""Custom holiday model for manual override of Colombian holidays.

Allows administrators to add holidays not covered by the algorithm
(e.g., new holidays created by law, civic holidays by decree).
Duplicates with algorithmic holidays are safely ignored via set union.
"""

from odoo import fields, models


class InsotechCustomHoliday(models.Model):
    """Manual holiday override per company."""

    _name = 'insotech.custom.holiday'
    _description = 'Festivo Personalizado'
    _order = 'date asc'

    name = fields.Char(
        string="Nombre del Festivo",
        required=True,
        help="Nombre descriptivo del festivo "
             "(ej: 'Día Cívico Municipal').",
    )
    date = fields.Date(
        string="Fecha",
        required=True,
        index=True,
        help="Fecha del festivo.",
    )
    company_id = fields.Many2one(
        'res.company',
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
        help="Empresa para la cual aplica este festivo.",
    )
