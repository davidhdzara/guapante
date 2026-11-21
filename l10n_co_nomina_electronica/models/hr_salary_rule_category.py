# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Categoría salarial: sección de «Conceptos de pago» (E11 pieza 2a, .287, doc 71c §4) y de «Cálculo del salario» (pieza 4a, .294, doc 74 §3)."""

from odoo import fields, models


class HrSalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    l10n_co_ne_seccion_concepto = fields.Selection(
        selection=[
            ('devengados', 'Devengados'),
            ('deducciones', 'Deducciones'),
            ('costo_empresa', 'Costo empresa'),
            ('bases', 'Bases de cotización y retención'),
        ],
        string='Sección en «Conceptos de pago»',
        help='Sección donde aparecen las líneas de las reglas de esta categoría: «Devengados» y «Deducciones» son las dos secciones de «Conceptos de '
             'pago»; «Costo empresa» no genera filas allí y suma al total en gris (aportes de la empresa, provisiones). En «Cálculo del salario» '
             '(solo lectura, soporte de auditoría) aparecen además las categorías de «Bases de cotización y retención» y, cada una en su sección, las de '
             '«Costo empresa». Vacío: sus líneas no se muestran en ninguna de las dos pestañas. La asignación es de esta categoría, no se hereda de '
             'la categoría padre.')
