# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Consolidacion mensual del IBC por empleado (H-017b).

Piso, techo y regla del 40% son por EMPLEADO Y MES, no por recibo: PILA reporta una
linea por cotizante y suma todo lo del mes (nomina, liquidacion parcial, bonificacion
salarial). Este registro es una FUNCION PURA del conjunto de recibos confirmados del
mes -- se recalcula completo cada vez, asi que no depende del orden de confirmacion.

No toca recibos ya confirmados (ni descuentos ni asientos): cada recibo conserva su IBC
"crudo" y aqui queda la diferencia contra el consolidado, auditable. PILA, UGPP y los
aportes patronales de la planilla leen este valor."""

from datetime import timedelta

from odoo import api, fields, models


class L10nCoIbcMensual(models.Model):
    _name = 'l10n.co.ibc.mensual'
    _check_company_auto = True
    _description = 'IBC consolidado por empleado y mes'
    _order = 'period desc, employee_id'

    company_id = fields.Many2one('res.company', required=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True)
    period = fields.Date(string='Mes', required=True, index=True,
                         help='Primer dia del mes consolidado.')
    payslip_ids = fields.Many2many(
        'hr.payslip', relation='l10n_co_ibc_mensual_payslip_rel',
        string='Recibos del mes', check_company=True)
    ibc_sp = fields.Monetary(string='IBC Salud y Pensión')
    ibc_arl = fields.Monetary(string='IBC ARL')
    ibc_paraf = fields.Monetary(string='IBC Parafiscales')
    dias_sp = fields.Integer(string='Días Salud y Pensión')
    dias_arl = fields.Integer(string='Días ARL')
    dias_paraf = fields.Integer(string='Días Parafiscales')
    ibc_sln = fields.Monetary(
        string='IBC de Días SLN',
        help='Parte del IBC de Salud y Pensión que corresponde a días de suspensión o licencia '
             'no remunerada (base de continuidad: último IBC prorrateado). Sobre ella el '
             'trabajador no paga su cuota; el empleador paga salud (sin exoneración) y la '
             'pensión patronal si la compañía así lo decide.')
    dias_sln = fields.Integer(string='Días SLN')
    ibc_recibos_sp = fields.Monetary(string='Suma IBC de los recibos (S+P)')
    ibc_recibos_arl = fields.Monetary(string='Suma IBC de los recibos (ARL)')
    ibc_recibos_paraf = fields.Monetary(string='Suma IBC de los recibos (Paraf.)')
    diferencia_sp = fields.Monetary(
        string='Diferencia Salud y Pensión', compute='_compute_diferencia', store=True,
        help='Consolidado menos la suma de lo que reportaron los recibos. Distinta de cero '
             'solo en meses con varios documentos (o piso/techo/40% que cambian al sumar): '
             'los recibos confirmados no se reescriben; ajustarlo es decisión de negocio.')
    diferencia_arl = fields.Monetary(compute='_compute_diferencia', store=True)
    diferencia_paraf = fields.Monetary(compute='_compute_diferencia', store=True)

    planilla_id = fields.Many2one(
        'l10n.co.pila.planilla', string='Última Planilla', ondelete='set null', check_company=True,
        help='Planilla PILA que usó este consolidado.')
    ibc_sp_planilla = fields.Monetary(string='IBC S+P en la Planilla')
    ibc_arl_planilla = fields.Monetary(string='IBC ARL en la Planilla')
    ibc_paraf_planilla = fields.Monetary(string='IBC Paraf. en la Planilla')
    requiere_planilla_n = fields.Boolean(
        string='Requiere Planilla N', compute='_compute_requiere_planilla_n', store=True,
        help='El IBC consolidado cambió después de generarse la planilla: si ya se '
             'presentó, hay que corregirla con una planilla tipo N.')

    _sql_constraints = [
        ('unico_empleado_mes', 'unique(company_id, employee_id, period)',
         'Ya existe el IBC consolidado de este empleado para ese mes.'),
    ]

    @api.depends('ibc_sp', 'ibc_arl', 'ibc_paraf',
                 'ibc_recibos_sp', 'ibc_recibos_arl', 'ibc_recibos_paraf')
    def _compute_diferencia(self):
        for rec in self:
            rec.diferencia_sp = rec.ibc_sp - rec.ibc_recibos_sp
            rec.diferencia_arl = rec.ibc_arl - rec.ibc_recibos_arl
            rec.diferencia_paraf = rec.ibc_paraf - rec.ibc_recibos_paraf

    @api.depends('planilla_id', 'ibc_sp', 'ibc_arl', 'ibc_paraf',
                 'ibc_sp_planilla', 'ibc_arl_planilla', 'ibc_paraf_planilla')
    def _compute_requiere_planilla_n(self):
        for rec in self:
            rec.requiere_planilla_n = bool(rec.planilla_id) and any(
                abs(a - b) > 0.5 for a, b in (
                    (rec.ibc_sp, rec.ibc_sp_planilla),
                    (rec.ibc_arl, rec.ibc_arl_planilla),
                    (rec.ibc_paraf, rec.ibc_paraf_planilla)))

    @api.model
    def _recibos_del_mes(self, company, employee, period):
        """Recibos confirmados del empleado cuyo ULTIMO dia cae en el mes (la liquidacion
        tiene date_from = inicio de contrato, por eso se usa date_to) y que traen IBC."""
        siguiente = (period.replace(day=28) + timedelta(days=4)).replace(day=1)
        slips = self.env['hr.payslip'].search([
            ('company_id', '=', company.id),
            ('employee_id', '=', employee.id),
            ('state', 'in', ('done', 'paid')),
            ('date_to', '>=', period), ('date_to', '<', siguiente),
        ], order='date_to, id')
        return slips.filtered(lambda s: s.line_ids.filtered(lambda l: l.code == 'CO_IBC_SP'))

    @api.model
    def _valores_sln(self, slips, ibc_sp, dias_sp):
        """Base y días SLN del mes, acotados al total de salud y pensión del consolidado."""
        ibc = sum(l.total for s in slips for l in s.line_ids if l.code == 'CO_IBC_SLN')
        dias = sum(s._ne_dias_sln() for s in slips)
        return {'ibc_sln': min(ibc, ibc_sp), 'dias_sln': int(min(dias, dias_sp))}

    @api.model
    def _refrescar(self, company, employee, period):
        """Recalcula (idempotente) el consolidado del empleado en el mes de `period`.
        Sin recibos con IBC, elimina el registro y devuelve uno vacio."""
        period = period.replace(day=1)
        existente = self.sudo().search([
            ('company_id', '=', company.id), ('employee_id', '=', employee.id),
            ('period', '=', period)])
        slips = self._recibos_del_mes(company, employee, period)
        if not slips:
            existente.unlink()
            return self.browse()

        def suma(codigo):
            return sum(l.total for s in slips for l in s.line_ids if l.code == codigo)

        ref = slips[-1]
        dias_mes = ref._rule_parameter('l10n_co_dias_mes_comercial', ref._ne_fecha_parametros())
        salarial = suma('CO_IBC_SALARIAL')
        remuneracion = suma('CO_IBC_REMUN')
        pactados = suma('CO_IBC_PACTADOS')
        incap = suma('CO_IBC_INCAP') + suma('CO_IBC_SLN')
        dias_sp = int(min(suma('CO_DIAS_SP'), dias_mes))
        dias_arl = int(min(suma('CO_DIAS_ARL'), dias_mes))
        dias_paraf = int(min(suma('CO_DIAS_PARAF'), dias_mes))
        ibc_sp = ref._ne_ibc_limites(salarial, incap, remuneracion, pactados, dias_sp)
        vals = {
            'payslip_ids': [(6, 0, slips.ids)],
            'ibc_sp': ibc_sp,
            'ibc_arl': ref._ne_ibc_limites(salarial, 0.0, remuneracion, pactados, dias_arl),
            'ibc_paraf': ref._ne_ibc_limites(salarial, 0.0, remuneracion, pactados, dias_paraf),
            'dias_sp': dias_sp, 'dias_arl': dias_arl, 'dias_paraf': dias_paraf,
            **self._valores_sln(slips, ibc_sp, dias_sp),
            'ibc_recibos_sp': suma('CO_IBC_SP'),
            'ibc_recibos_arl': suma('CO_IBC_ARL'),
            'ibc_recibos_paraf': suma('CO_IBC_PARAF'),
        }
        if existente:
            existente.write(vals)
            return existente
        return self.sudo().create(dict(
            vals, company_id=company.id, employee_id=employee.id, period=period))
