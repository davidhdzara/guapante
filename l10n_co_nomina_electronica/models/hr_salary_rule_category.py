# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Categoría salarial: sección de «Conceptos de pago» (E11 pieza 2a, .287, doc 71c §4)."""

from odoo import fields, models


class HrSalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    l10n_co_ne_seccion_concepto = fields.Selection(
        selection=[
            ('devengados', 'Devengados'),
            ('deducciones', 'Deducciones'),
            ('costo_empresa', 'Costo empresa'),
        ],
        string='Sección en «Conceptos de pago»',
        help='Sección donde aparecen las líneas de las reglas de esta categoría en «Conceptos de pago»: «Devengados» y «Deducciones» son las '
             'dos secciones de la lista; «Costo empresa» no genera filas y suma al total en gris (aportes de la empresa, provisiones). '
             'Vacío: sus líneas no se muestran allí. La asignación es de esta categoría, no se hereda de la categoría padre.')
