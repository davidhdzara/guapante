# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Registro de planillas PILA generadas (H-017b).

Permite verificar que una planilla de correccion (tipo N) se presente con el MISMO
operador de la planilla original, y marcar cuando un documento tardio cambia el IBC
consolidado de un mes ya presentado ('requiere planilla N')."""

from odoo import api, fields, models


class L10nCoPilaPlanilla(models.Model):
    _name = 'l10n.co.pila.planilla'
    _check_company_auto = True
    _description = 'Planilla PILA generada'
    _order = 'period desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    period = fields.Date(string='Mes', required=True, help='Primer dia del mes cotizado.')
    tipo_planilla = fields.Char(string='Tipo', required=True)
    operador_code = fields.Char(
        string='Operador', required=True,
        help='Codigo del operador de informacion con el que se genero.')
    numero_planilla = fields.Char(
        string='Número de Planilla',
        help='Numero que asigna el operador al presentarla. Complételo: lo exige la planilla '
             'de corrección (tipo N) que la tome como original.')
    fecha_pago = fields.Date(string='Fecha de Pago')
    planilla_original_id = fields.Many2one(
        'l10n.co.pila.planilla', string='Planilla Corregida', ondelete='restrict',
        check_company=True)
    file_name = fields.Char(string='Archivo')
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    ibc_mensual_ids = fields.One2many('l10n.co.ibc.mensual', 'planilla_id', string='Cotizantes')
    cotizantes = fields.Integer(compute='_compute_cotizantes')
    requiere_correccion = fields.Boolean(
        compute='_compute_cotizantes',
        help='Algún IBC consolidado cambió después de generar esta planilla.')

    @api.depends('tipo_planilla', 'period', 'numero_planilla')
    def _compute_name(self):
        for rec in self:
            rec.name = 'PILA %s %s%s' % (
                rec.tipo_planilla or '', rec.period.strftime('%Y-%m') if rec.period else '',
                ' #%s' % rec.numero_planilla if rec.numero_planilla else '')

    @api.depends('ibc_mensual_ids.requiere_planilla_n')
    def _compute_cotizantes(self):
        for rec in self:
            rec.cotizantes = len(rec.ibc_mensual_ids)
            rec.requiere_correccion = any(rec.ibc_mensual_ids.mapped('requiere_planilla_n'))
