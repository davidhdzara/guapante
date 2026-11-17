# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-164 (CST Art. 307): la prima no es salario ni factor salarial -> no entra al IBC de la
liquidacion ni genera salud/pension. Se prueba comparando la liquidacion con y sin la regla
CO_LIQ_PRIMA: el IBC salarial, el IBC de salud y pension y los descuentos no cambian; solo el
neto sube exactamente el valor de la prima."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

RETIRO = date(2026, 8, 15)


@tagged('post_install', '-at_install')
class TestLiquidacionPrimaIbc(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Prima IBC Liquidación'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Prima IBC', 'country_id': cls.env.ref('base.co').id})
        cls.liquidacion = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')

    def _liquidacion(self):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Prima IBC', 'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Prima IBC', 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2024, 3, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Liquidación Prima IBC', 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.liquidacion.id,
            'date_from': contract.date_start, 'date_to': RETIRO})

    def _total(self, slip, code):
        return sum(slip.line_ids.filtered(lambda l: l.code == code).mapped('total'))

    def test_la_prima_no_entra_al_ibc_ni_a_salud_y_pension_de_la_liquidacion(self):
        slip = self._liquidacion()
        slip.compute_sheet()
        prima = self._total(slip, 'CO_LIQ_PRIMA')
        self.assertGreater(prima, 0.0)
        salarios = self._total(slip, 'CO_LIQ_SALARIOS')
        # Sin vacaciones ni licencias del tramo, el IBC salarial es solo el salario del tramo.
        self.assertAlmostEqual(self._total(slip, 'CO_IBC_SALARIAL'), salarios, delta=0.01)
        ibc_sp = self._total(slip, 'CO_IBC_SP')
        salud = self._total(slip, 'CO_LIQ_SALUD')
        pension = self._total(slip, 'CO_LIQ_PENSION')
        neto_con = self._total(slip, 'CO_LIQ_NETO')
        rete_con = self._total(slip, 'CO_LIQ_RETE')

        regla = self.env['hr.salary.rule'].search(
            [('code', '=', 'CO_LIQ_PRIMA'), ('struct_id', '=', self.liquidacion.id)], limit=1)
        regla.active = False
        slip.compute_sheet()
        self.assertFalse(self._total(slip, 'CO_LIQ_PRIMA'))
        self.assertAlmostEqual(self._total(slip, 'CO_IBC_SALARIAL'), salarios, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_IBC_SP'), ibc_sp, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_LIQ_SALUD'), salud, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_LIQ_PENSION'), pension, delta=0.01)
        # El neto solo cambia en el valor de la prima y en la retencion en la fuente (que si
        # depende de la prima; los descuentos de salud y pension, arriba, no): neto_con - neto_sin
        # = prima + (retencion_con - retencion_sin), con la retencion en negativo.
        rete_sin = self._total(slip, 'CO_LIQ_RETE')
        self.assertAlmostEqual(
            neto_con - self._total(slip, 'CO_LIQ_NETO'), prima + (rete_con - rete_sin), delta=0.01)
