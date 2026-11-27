# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Día de descanso del EMPLEADO pactado por escrito (H-F1-07, doc 92; decisiones D-07 del TL del 22-nov).

Ley 2466 de 2025, art. 14 (modifica el art. 179 del CST), parágrafo 3: «las partes del contrato de trabajo podrán convenir por escrito que su día de descanso sea distinto al domingo»; si no se pacta expresamente
en el contrato u otrosí, se presume que es el domingo (texto leído parcialmente: el literal íntegro es NO VERIFICADO). Este modelo registra ese pacto: UNA fila por vigencia, con el día de la semana, la fecha de
firma, la fecha de fin (opcional) y el documento firmado (contrato u otrosí).

Cuelga del EMPLEADO y no del contrato (mismo criterio del pacto de desalarización, .302): al renovar el contrato el pacto no se pierde y en Odoo 19 ``hr.contract`` no existe. Cubre una fecha si cae entre la
fecha de firma y la de fin (vacía = vigente) SIEMPRE QUE tenga el documento adjunto: se puede guardar sin documento (para cargarlo después) pero entonces NO cubre («pacto sin soporte»): el par. 3 exige el escrito y
la prueba es del empleador. Sin un registro que la cubra, el día de descanso es el DOMINGO por la presunción de la ley, no por un valor por defecto del código (``HrEmployee._ne_dia_de_descanso``)."""

from datetime import date as _date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

DOMINGO = 6          # ``date.weekday()``: 0 = lunes ... 6 = domingo
DIAS_DE_LA_SEMANA = [('0', 'Lunes'), ('1', 'Martes'), ('2', 'Miércoles'), ('3', 'Jueves'), ('4', 'Viernes'), ('5', 'Sábado'), ('6', 'Domingo')]


class L10nCoEmployeeDescanso(models.Model):
    _name = 'l10n.co.employee.descanso'
    _inherit = ['l10n.co.adjunto.vinculado']
    _description = 'Día de descanso pactado por escrito del empleado'
    _order = 'employee_id, fecha_firma desc, id'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, ondelete='cascade', index=True)
    dia_semana = fields.Selection(
        DIAS_DE_LA_SEMANA, string='Día de descanso', required=True,
        help='Día de la semana pactado por escrito como día de descanso obligatorio del empleado (Ley 2466 de 2025, art. 14, par. 3). Sin un pacto vigente con el documento firmado, el descanso es el domingo.')
    fecha_firma = fields.Date(string='Fecha de firma', required=True, help='Desde cuándo rige el pacto (la firma del contrato u otrosí).')
    fecha_fin = fields.Date(string='Fecha de fin', help='Opcional. Vacía = el pacto sigue vigente.')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'l10n_co_employee_descanso_attachment_rel', 'descanso_id', 'attachment_id', string='Documento firmado',
        help='El contrato u otrosí que pacta el día de descanso. Se puede guardar el registro sin documento, pero mientras no lo tenga NO cubre ninguna fecha: el descanso sigue siendo el domingo (el recibo avisa «pacto sin soporte»).')

    @api.constrains('fecha_firma', 'fecha_fin')
    def _check_fechas(self):
        for registro in self:
            if registro.fecha_fin and registro.fecha_firma and registro.fecha_fin < registro.fecha_firma:
                raise ValidationError(_('La fecha de fin del día de descanso pactado de %(empleado)s no puede ser anterior a la fecha de firma.', empleado=registro.employee_id.name))

    @api.constrains('employee_id', 'fecha_firma', 'fecha_fin')
    def _check_sin_traslape(self):
        """Un solo día de descanso por fecha: dos registros del mismo empleado no pueden tener vigencias que se crucen."""
        for registro in self:
            if not registro.fecha_firma:
                continue
            otros = self.sudo().search([
                ('employee_id', '=', registro.employee_id.id), ('id', '!=', registro.id), ('fecha_firma', '<=', registro.fecha_fin or _date.max),
                '|', ('fecha_fin', '=', False), ('fecha_fin', '>=', registro.fecha_firma)])
            if otros:
                raise ValidationError(_(
                    'El día de descanso pactado de %(empleado)s se cruza con otro registro (%(otro_desde)s a %(otro_hasta)s): dos pactos no pueden regir la misma fecha. Termine el anterior con su fecha de fin.',
                    empleado=registro.employee_id.name, otro_desde=otros[0].fecha_firma, otro_hasta=otros[0].fecha_fin or _('vigente')))

    @api.model
    def _vigente(self, empleado, fecha):
        """El registro del empleado que rige ``fecha`` (con o sin documento), o vacío. Se lee con ``sudo``: solo para saber el día de descanso al calcular o mostrar un aviso, con cualquier usuario de nómina."""
        return self.sudo().search([
            ('employee_id', '=', empleado.id), ('fecha_firma', '<=', fecha), '|', ('fecha_fin', '=', False), ('fecha_fin', '>=', fecha)], limit=1)
