# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""E-5 (doc 59 §22): el boton nativo «Mark as paid» del lote no fija la fecha de pago de forma silenciosa.

``hr.payslip.run.action_paid`` llama a ``action_payslip_paid``, que escribe ``paid_date = hoy`` sin preguntar. Con la fuente de la fecha de
pago «Fecha de pago del recibo» esa fecha decide el mes del documento de nomina electronica y ``FechasPagos``: un lote pagado el 28-oct y
marcado el 2-nov pasaria al documento de noviembre. Para companias colombianas con esa fuente el boton abre el asistente
«Registrar fecha de pago» (fecha editable, no futura) con los recibos del lote; el resto (fuente «contabilidad», otros paises) conserva
el comportamiento nativo.

Volver a borrador (.333): el nativo ``action_draft`` del lote escribe ``state = 'draft'`` en sus recibos sin pasar por su cancelacion: el asiento
sigue ligado al recibo (al confirmar de nuevo no se crea otro) y la cuota de libranza sigue aplicada. En companias colombianas se detiene y pide
cancelar recibo por recibo, que si reversa las dos cosas."""

from odoo import _, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_draft(self):
        self._ne_validar_volver_a_borrador()
        colombia = self.slip_ids._ne_solo_colombia()
        res = super().action_draft()
        colombia._ne_olvidar_pago()          # el lote no pasa por ``action_payslip_draft``
        return res

    def _ne_validar_volver_a_borrador(self):
        """Los cancelados ya se reversaron; los pagados los rechaza el nativo con su propio mensaje."""
        recibos = self.slip_ids._ne_solo_colombia().filtered(lambda s: s.state not in ('cancel', 'paid'))
        con_libranza = set(recibos._ne_filas_de_libranza(aplicadas=True).slip_id.ids)
        afectados = recibos.filtered(lambda s: s.move_id or s.id in con_libranza)
        if afectados:
            raise UserError(_(
                'No se puede devolver el lote a borrador: %(total)s recibo(s) tienen asiento contable o cuota de libranza ya aplicada, y desde el lote no se reversa ninguno de los dos. '
                'Cancele esos recibos uno por uno (botón «Cancelar» del recibo; si está confirmado lo hace el administrador de nómina) y vuelva a intentarlo. Recibos: %(recibos)s.',
                total=len(afectados), recibos=', '.join(afectados.mapped('display_name'))))

    def action_paid(self):
        if not self.env.context.get('ne_fecha_pago_definida'):
            recibos = self.slip_ids.filtered(
                lambda s: s.state == 'done' and s.company_id._ne_es_colombia()
                and s.company_id.l10n_co_ne_fuente_fecha_pago == 'recibo')
            if recibos:
                return {
                    'type': 'ir.actions.act_window', 'name': _('Registrar fecha de pago'),
                    'res_model': 'hr.payslip.registrar.pago', 'view_mode': 'form', 'target': 'new',
                    'context': {'active_model': 'hr.payslip', 'active_ids': recibos.ids, 'ne_payslip_run_ids': self.ids}}
        return super().action_paid()
