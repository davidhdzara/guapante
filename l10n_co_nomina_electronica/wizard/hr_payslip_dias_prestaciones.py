# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Días de prima y de vacaciones compensadas (Q-19, doc 116, .332): la nómina electrónica pide los días y la novedad en pesos no los lleva.

«Conceptos de pago» solo ofrece novedades con regla y estas no la tienen (no cambian valores), por eso se registran aquí: en un recibo en borrador o confirmado
que aún no se ha reportado, o en uno reportado con una nota de ajuste «Reemplazar» sin enviar (.335). En uno confirmado no se recalcula nada: ni líneas, ni neto, ni asiento (``HrPayslip._ne_registrar_dias``)."""

from odoo import api, fields, models


class HrPayslipDiasPrestaciones(models.TransientModel):
    _name = 'hr.payslip.dias.prestaciones'
    _description = 'Registrar días de prima y vacaciones compensadas'

    payslip_id = fields.Many2one('hr.payslip', string='Recibo', required=True, readonly=True, ondelete='cascade')
    paga_prima = fields.Boolean(compute='_compute_paga')
    paga_vacaciones = fields.Boolean(compute='_compute_paga')
    dias_prima = fields.Float(string='Días de la prima', help='Días a los que corresponde la prima que paga este recibo (Anexo DIAN, NIE117).')
    dias_vacaciones = fields.Float(string='Días de vacaciones compensadas', help='Días de vacaciones compensadas en dinero que paga este recibo (Anexo DIAN, NIE115).')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        recibo = self.env['hr.payslip'].browse(res.get('payslip_id') or self.env.context.get('default_payslip_id'))
        if recibo:
            res.update(dias_prima=recibo._ne_dias_registrados('CO_PRIMA'), dias_vacaciones=recibo._ne_dias_registrados('CO_VAC_COMP'))
        return res

    @api.depends('payslip_id')
    def _compute_paga(self):
        for asistente in self:
            codigos = asistente.payslip_id._ne_novedades_que_piden_dias() if asistente.payslip_id else set()
            asistente.paga_prima = 'CO_PRIMA' in codigos
            asistente.paga_vacaciones = 'CO_VAC_COMP' in codigos

    def action_registrar_dias(self):
        self.ensure_one()
        self.payslip_id._ne_registrar_dias({'CO_PRIMA': self.dias_prima, 'CO_VAC_COMP': self.dias_vacaciones})
        return {'type': 'ir.actions.act_window_close'}
