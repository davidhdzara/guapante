# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Incapacidad comun: vinculo "es prorroga de" entre ausencias (M4 punto 5, doc 50; H-F1-01, doc 84).

hr.leave nativo no trae diagnostico ni vinculo entre ausencias (revisado en hr_holidays real de staging; solo `notes`). Se agrega UN dato: de que incapacidad anterior es prorroga esta, y desde
H-F1-01 ES la marca de «misma enfermedad» que decide que incapacidades forman una cadena: el tramo de pago (2 dias del empleador, 3 a 90, 91 en adelante) se cuenta desde el inicio de la INICIAL.
Norma de la prorroga: Decreto 1333 de 2018, art. 3 (publicado el 27-jul-2018) y, sustituido ese Titulo, Decreto 1427 de 2022, art. 2.2.3.3.2, paragrafo 1: existe prorroga cuando una nueva
incapacidad se origina por la misma enfermedad o lesion, o por otra que tenga relacion directa con ella, aunque cambie el codigo CIE, siempre que no haya una interrupcion mayor a 30 dias
calendario. La interrupcion maxima es el parametro ``l10n_co_dias_interrupcion_prorroga`` (30). El CIE no se guarda: la relacion entre enfermedades es un juicio medico que el modulo no valida;
lo marca quien registra la incapacidad con el certificado de la EPS a la vista."""

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

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
        copy=False, tracking=True,
        domain="[('employee_id', '=', employee_id), ('id', '!=', id),"
               " ('holiday_status_id.work_entry_type_id.code', '=', 'CO_INC_COMUN')]",
        help='Incapacidad común anterior de la que esta es prórroga: la misma enfermedad o una que tenga relación directa con ella, aunque cambie el código CIE, '
             'con una interrupción de a lo sumo 30 días calendario (Decreto 1427 de 2022, art. 2.2.3.3.2, parágrafo 1; antes Decreto 1333 de 2018, art. 3). '
             'Las incapacidades vinculadas forman UNA cadena: el pago por tramos (2 días del empleador, 3 a 90, 91 en adelante) se cuenta desde el inicio de la '
             'inicial. Sin vínculo, cada incapacidad empieza su propio conteo. Márquela con el certificado de la EPS a la vista.',
    )
    l10n_co_ne_prorroga_aviso = fields.Char(
        string='Aviso de prórroga', compute='_compute_l10n_co_ne_prorroga_aviso',
        help='Solo para la vista: aviso (no bloquea) cuando hay una incapacidad común anterior del mismo empleado que terminó dentro de la interrupción máxima y esta no está marcada como su prórroga.')

    @api.depends('holiday_status_id.work_entry_type_id.code', 'employee_company_id')
    def _compute_l10n_co_ne_es_incapacidad_comun(self):
        for leave in self:
            leave.l10n_co_ne_es_incapacidad_comun = (
                leave.holiday_status_id.work_entry_type_id.code == CODIGO_INCAPACIDAD_COMUN
                and leave.employee_company_id._ne_es_colombia()
                if leave.employee_company_id else False)

    @api.model
    def _ne_interrupcion_maxima_prorroga(self, fecha):
        """Días calendario de interrupción que admite la prórroga a la ``fecha`` (parámetro ``l10n_co_dias_interrupcion_prorroga``, 30). OBLIGATORIO: sin el parámetro, un error claro que lo nombra."""
        try:
            valor = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_co_dias_interrupcion_prorroga', fecha)
        except UserError:                     # el nativo lanza UserError si no hay valor a esa fecha: se reemplaza por un mensaje que nombra el parametro y dice que hacer
            valor = None
        if valor is None:
            raise UserError(_(
                'Falta el parámetro de nómina «Colombia: Incapacidad Común, Interrupción Máxima para Prórroga (Días)» (código l10n_co_dias_interrupcion_prorroga) para el %(fecha)s. '
                'Actualice el módulo de nómina electrónica o créelo en Nómina > Configuración > Parámetros de reglas.', fecha=fecha))
        return int(valor)

    @api.depends('employee_id', 'request_date_from', 'l10n_co_ne_es_incapacidad_comun', 'l10n_co_ne_prorroga_de_id')
    def _compute_l10n_co_ne_prorroga_aviso(self):
        """«¿Es prórroga de …?»: hay una incapacidad común anterior del mismo empleado que terminó a lo sumo ``interrupción máxima`` días antes y esta no está vinculada. No bloquea ni pone un valor
        por defecto: quien registra decide con el certificado de la EPS."""
        for leave in self:
            leave.l10n_co_ne_prorroga_aviso = False
            if not (leave.l10n_co_ne_es_incapacidad_comun and leave.employee_id and leave.request_date_from) or leave.l10n_co_ne_prorroga_de_id:
                continue
            try:
                interrupcion = self._ne_interrupcion_maxima_prorroga(leave.request_date_from)
            except UserError as error:
                leave.l10n_co_ne_prorroga_aviso = error.args[0]
                continue
            anterior = self.search([
                ('employee_id', '=', leave.employee_id.id), ('id', '!=', leave._origin.id or 0),
                ('holiday_status_id.work_entry_type_id.code', '=', CODIGO_INCAPACIDAD_COMUN),
                ('state', 'in', ('confirm', 'validate1', 'validate')),
                ('request_date_to', '<', leave.request_date_from),
                ('request_date_to', '>=', leave.request_date_from - timedelta(days=interrupcion + 1))], order='request_date_to desc', limit=1)
            if anterior:
                leave.l10n_co_ne_prorroga_aviso = _(
                    '¿Es prórroga de «%(ausencia)s» (hasta el %(fecha)s)? Si es la misma enfermedad o una relacionada, márquelo en «Prórroga de»: así el pago por tramos sigue desde el inicio '
                    'de la incapacidad inicial. Sin la marca, esta incapacidad empieza su propio conteo.',
                    ausencia=anterior.display_name, fecha=anterior.request_date_to)

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
            # H-F1-01: la interrupcion (dias calendario libres entre las dos) no puede superar el parametro (30).
            libres = (leave.request_date_from - anterior.request_date_to).days - 1
            maxima = self._ne_interrupcion_maxima_prorroga(leave.request_date_from)
            if libres > maxima:
                raise ValidationError(_(
                    'Entre la incapacidad anterior (hasta %(hasta)s) y esta (desde %(desde)s) hay %(libres)s días de interrupción, más de los %(maxima)s que admite la prórroga '
                    '(parámetro l10n_co_dias_interrupcion_prorroga; Decreto 1427 de 2022, art. 2.2.3.3.2, parágrafo 1). Son incapacidades distintas: quite el vínculo.',
                    hasta=anterior.request_date_to, desde=leave.request_date_from, libres=libres, maxima=maxima))
            # Una incapacidad tiene A LO SUMO una prorroga siguiente (la cadena es una lista, no un arbol): si no, las posiciones de los tramos se contarian dos veces.
            otras = self.search_count([('l10n_co_ne_prorroga_de_id', '=', anterior.id), ('id', '!=', leave.id)])
            if otras:
                raise ValidationError(_(
                    '«%(anterior)s» ya tiene una prórroga. Una incapacidad solo puede tener una prórroga siguiente: la cadena de prórrogas es una lista.', anterior=anterior.display_name))
        if self._has_cycle('l10n_co_ne_prorroga_de_id'):
            raise ValidationError(_('Una incapacidad no puede ser prórroga de sí misma ni formar un ciclo.'))
