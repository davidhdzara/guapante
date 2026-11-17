# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""E-5 (doc 59 §22): el boton nativo «Mark as paid» del lote no fija la fecha de pago de forma silenciosa.

``hr.payslip.run.action_paid`` llama a ``action_payslip_paid``, que escribe ``paid_date = hoy`` sin preguntar. Con la fuente de la fecha de
pago «Fecha de pago del recibo» esa fecha decide el mes del documento de nomina electronica y ``FechasPagos``: un lote pagado el 28-oct y
marcado el 2-nov pasaria al documento de noviembre. Para companias colombianas con esa fuente el boton abre el asistente
«Registrar fecha de pago» (fecha editable, no futura) con los recibos del lote; el resto (fuente «contabilidad», otros paises) conserva
el comportamiento nativo."""

from odoo import _, models


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

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
