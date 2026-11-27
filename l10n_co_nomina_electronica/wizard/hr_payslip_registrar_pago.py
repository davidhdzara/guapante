# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Registrar fecha de pago (doc 53 §20.3, D18): marca recibos como pagados con una fecha real editable (desatraso masivo).

Para compañías cuya fuente de la fecha de pago es 'recibo' y, con «Pagos de Contabilidad», solo para recibos de neto 0 (CC-08: no hay
pago que conciliar). Reutiliza la acción nativa ``action_payslip_paid`` y luego fija la fecha elegida (el nativo pone hoy)."""

from odoo import _, fields, models
from odoo.exceptions import UserError


class HrPayslipRegistrarPago(models.TransientModel):
    _name = 'hr.payslip.registrar.pago'
    _description = 'Registrar fecha de pago de recibos de nómina'

    payslip_ids = fields.Many2many('hr.payslip', string='Recibos', required=True)
    fecha = fields.Date(string='Fecha de pago', required=True, default=fields.Date.context_today,
                        help='Fecha real del pago al empleado. Decide el mes del documento de nómina electrónica.')

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'hr.payslip' and self.env.context.get('active_ids'):
            res['payslip_ids'] = [(6, 0, self.env.context['active_ids'])]
        return res

    def action_registrar_pago(self):
        self.ensure_one()
        recibos = self.payslip_ids
        if self.fecha > fields.Date.context_today(self):
            raise UserError(_('La fecha de pago no puede ser futura.'))
        a_mano = recibos.filtered(lambda s: s._ne_fecha_se_registra_a_mano())
        # Un recibo de neto 0 ya marcado como pagado con el botón nativo todavía no tiene fecha registrada: se le puede registrar.
        sin_registrar = a_mano.filtered(lambda s: s.state == 'paid' and not s.l10n_co_ne_fecha_pago_registrada)
        no_listos = (recibos - sin_registrar).filtered(lambda s: s.state != 'done')
        if no_listos:
            raise UserError(_(
                'Solo se registra el pago de recibos en estado "Hecho". No lo están: %(recibos)s.',
                recibos=', '.join(no_listos.mapped('display_name'))))
        de_contabilidad = (recibos - a_mano).filtered(lambda s: s.company_id.l10n_co_ne_fuente_fecha_pago != 'recibo')
        if de_contabilidad:
            raise UserError(_(
                'La fecha de pago de estas compañías no sale del recibo (Ajustes > Nómina > "Fuente de la fecha de '
                'pago"): %(companias)s. Recibos: %(recibos)s. Con "Pagos de Contabilidad" solo se registra a mano la de un recibo con neto 0.',
                companias=', '.join(de_contabilidad.company_id.mapped('name')),
                recibos=', '.join(de_contabilidad.mapped('display_name'))))
        recibos.action_payslip_paid()
        # Desde «Marcar como pagado» del lote (E-5): el lote pasa a «pagado» con el nativo (marca tambien los recibos de otras
        # companias o fuentes) y LUEGO se fija la fecha elegida (el nativo pone hoy).
        lotes = self.env['hr.payslip.run'].browse(self.env.context.get('ne_payslip_run_ids') or [])
        if lotes:
            lotes.with_context(ne_fecha_pago_definida=True).action_paid()
        recibos.write({'paid_date': self.fecha})
        a_mano.write({'l10n_co_ne_fecha_pago_registrada': self.fecha})
        return {'type': 'ir.actions.act_window_close'}
