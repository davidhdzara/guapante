# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Distribucion por tercero de una linea de nomina.

Una regla salarial produce UNA linea de recibo, pero embargos y libranzas se
pagan a varios terceros. Este modelo guarda, por nomina, cuanto de la linea
corresponde a cada tercero/asignacion salarial. La suma de `amount` por
regla es igual al total de la linea (la regla lo calcula con el mismo metodo).
"""

from odoo import fields, models


class L10nCoPayslipTercero(models.Model):
    _name = 'l10n.co.payslip.tercero'
    _check_company_auto = True
    _description = 'Distribución por tercero de una línea de nómina'
    _order = 'slip_id, rule_code, id'

    slip_id = fields.Many2one(
        'hr.payslip', required=True, ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='slip_id.company_id', store=True)
    currency_id = fields.Many2one(related='slip_id.company_id.currency_id')
    rule_code = fields.Char(required=True)
    partner_id = fields.Many2one('res.partner', string='Tercero')
    attachment_id = fields.Many2one(
        'hr.salary.attachment', string='Asignación Salarial', ondelete='restrict')
    amount = fields.Monetary(string='Descontado', currency_field='currency_id')
    arrears_paid = fields.Monetary(
        string='Atraso Recuperado', currency_field='currency_id',
        help='Parte de lo descontado que corresponde a saldo pendiente.')
    deferred = fields.Monetary(
        string='No Descontado', currency_field='currency_id',
        help='Cuota del período que no se pudo descontar por el tope y pasa '
             'a saldo pendiente.')
    applied = fields.Boolean(
        string='Aplicado', default=False, copy=False,
        help='Ya se reflejó en lo pagado y el saldo pendiente de la '
             'asignación salarial (al confirmar la nómina).')
