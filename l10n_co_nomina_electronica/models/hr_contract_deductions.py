# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Extensión de hr.contract con campos de deducciones fijas mensuales.

Permite configurar en el contrato las deducciones recurrentes que antes
requerían ingreso manual en cada nómina: libranzas, cuota sindical, AFC,
pensión voluntaria, plan complementario de salud, cooperativa y educación.

Las reglas salariales correspondientes leen estos campos automáticamente
y permiten sobreescritura puntual mediante inputs manuales en la nómina.
"""

from odoo import fields, models


class HrContractDeductions(models.Model):
    """Deducciones fijas mensuales configuradas en el contrato."""

    _inherit = 'hr.contract'

    # ──────────────────────────────────────────────────────────────────
    # Deducciones Legales
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_libranza = fields.Monetary(
        string='Libranza Mensual',
        currency_field='currency_id',
        help='Valor mensual de descuento por libranza. '
             'Se aplica automaticamente en cada nomina. '
             'Si se ingresa un valor manual en la nomina, este tiene prioridad.',
    )
    l10n_co_ne_sindicato = fields.Monetary(
        string='Cuota Sindical Mensual',
        currency_field='currency_id',
        help='Cuota sindical fija mensual. '
             'Se aplica automaticamente en cada nomina.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Ahorro y Previsión
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_afc = fields.Monetary(
        string='AFC Mensual',
        currency_field='currency_id',
        help='Ahorro para el Fomento de la Construccion (AFC). '
             'Art. 126-4 ET. Se deduce automaticamente cada mes.',
    )
    l10n_co_ne_pension_voluntaria = fields.Monetary(
        string='Pension Voluntaria Mensual',
        currency_field='currency_id',
        help='Aporte voluntario a fondo de pensiones. '
             'Art. 126-1 ET. Se deduce automaticamente cada mes.',
    )
    l10n_co_ne_plan_complementario = fields.Monetary(
        string='Plan Complementario Salud',
        currency_field='currency_id',
        help='Plan complementario de salud (medicina prepagada). '
             'Se deduce automaticamente cada mes.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Otros
    # ──────────────────────────────────────────────────────────────────
    l10n_co_ne_cooperativa = fields.Monetary(
        string='Cooperativa Mensual',
        currency_field='currency_id',
        help='Cuota mensual de cooperativa o fondo de empleados. '
             'Se deduce automaticamente cada mes.',
    )
    l10n_co_ne_educacion = fields.Monetary(
        string='Descuento Educacion',
        currency_field='currency_id',
        help='Descuento mensual por credito educativo o convenio. '
             'Se deduce automaticamente cada mes.',
    )
