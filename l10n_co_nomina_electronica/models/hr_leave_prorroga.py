# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Incapacidad comun: vinculo "es prorroga de" entre ausencias (M4 punto 5, doc 50).

hr.leave nativo no trae diagnostico ni vinculo entre ausencias (revisado en hr_holidays real de
staging; solo `notes`). Se agrega UN dato: de que incapacidad anterior es prorroga esta. Es solo el dato:
no cambia el motor ni fija ningun plazo (el plazo de interrupcion, l10n_co_dias_interrupcion_prorroga,
sigue en 0 hasta que David confirme la norma)."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

CODIGO_INCAPACIDAD_COMUN = 'CO_INC_COMUN'


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    l10n_co_ne_es_incapacidad_comun = fields.Boolean(
        compute='_compute_l10n_co_ne_es_incapacidad_comun',
        help='Ausencia de tipo Incapacidad Comun de una compania colombiana (solo para la vista).')
    l10n_co_ne_prorroga_de_id = fields.Many2one(
        comodel_name='hr.leave',
        string='Prórroga de',
        ondelete='set null',
        copy=False,
        domain="[('employee_id', '=', employee_id), ('id', '!=', id),"
               " ('holiday_status_id.work_entry_type_id.code', '=', 'CO_INC_COMUN')]",
        help='Incapacidad común anterior de la que esta es prórroga (misma enfermedad o una '
             'relacionada). Solo registra el vínculo.',
    )

    @api.depends('holiday_status_id.work_entry_type_id.code', 'employee_company_id')
    def _compute_l10n_co_ne_es_incapacidad_comun(self):
        for leave in self:
            leave.l10n_co_ne_es_incapacidad_comun = (
                leave.holiday_status_id.work_entry_type_id.code == CODIGO_INCAPACIDAD_COMUN
                and leave.employee_company_id._ne_es_colombia()
                if leave.employee_company_id else False)

    @api.constrains('l10n_co_ne_prorroga_de_id')
    def _check_l10n_co_ne_prorroga(self):
        for leave in self.filtered('l10n_co_ne_prorroga_de_id'):
            anterior = leave.l10n_co_ne_prorroga_de_id
            if anterior.employee_id != leave.employee_id:
                raise ValidationError(_(
                    'La ausencia de %(emp)s no puede ser prórroga de una ausencia de %(otro)s: '
                    'la incapacidad anterior debe ser del mismo empleado.',
                    emp=leave.employee_id.name, otro=anterior.employee_id.name))
            for ausencia in (leave, anterior):
                if ausencia.holiday_status_id.work_entry_type_id.code != CODIGO_INCAPACIDAD_COMUN:
                    raise ValidationError(_(
                        'La prórroga solo aplica a incapacidades de origen común: "%(ausencia)s" '
                        'es de tipo "%(tipo)s".',
                        ausencia=ausencia.display_name, tipo=ausencia.holiday_status_id.name))
            if anterior.request_date_to >= leave.request_date_from:
                raise ValidationError(_(
                    'La incapacidad anterior (hasta %(hasta)s) debe terminar antes de que empiece '
                    'esta (desde %(desde)s).',
                    hasta=anterior.request_date_to, desde=leave.request_date_from))
        if self._has_cycle('l10n_co_ne_prorroga_de_id'):
            raise ValidationError(_('Una incapacidad no puede ser prórroga de sí misma ni formar un ciclo.'))
