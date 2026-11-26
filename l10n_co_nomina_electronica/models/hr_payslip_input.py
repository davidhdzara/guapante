# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Novedades del recibo (``hr.payslip.input``): la hoja de cálculo se actualiza sola (.283, doc 68 §14).

Defecto (orden de David; producción, SLIP/087): una novedad guardada (``CO_BONIF_NOSAL`` 200.000) no generaba su línea hasta pulsar «Calcular
hoja». Ahora, al crear, editar o borrar una novedad de un recibo en borrador o en espera que ya tiene la hoja calculada, el recibo se recalcula
con ``compute_sheet()`` (una vez por recibo y por operación). La lógica está en ``HrPayslip._ne_recalcular_hoja_por_novedad``.

El archivo nativo ``hr_payroll/models/hr_payslip_input.py`` solo define campos (sin ``create``/``write``/``unlink`` ni constraints: lectura de TL)."""

from odoo import api, models


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    # Lo que cambia el cálculo de una novedad: el valor, su tipo (su código) y el recibo al que pertenece. ``name`` y ``sequence`` no.
    _NE_CAMPOS_QUE_RECALCULAN = frozenset({'amount', 'input_type_id', 'payslip_id'})

    @api.model_create_multi
    def create(self, vals_list):
        entradas = super().create(vals_list)
        entradas.payslip_id._ne_recalcular_hoja_por_novedad()
        return entradas

    def write(self, vals):
        cambia_el_calculo = bool(self._NE_CAMPOS_QUE_RECALCULAN & set(vals))
        recibos_antes = self.payslip_id
        res = super().write(vals)
        if cambia_el_calculo:
            # Con payslip_id distinto también el recibo anterior queda con la hoja vieja.
            (recibos_antes | self.payslip_id)._ne_recalcular_hoja_por_novedad()
        return res

    def unlink(self):
        recibos = self.payslip_id
        res = super().unlink()
        recibos._ne_recalcular_hoja_por_novedad()
        return res
