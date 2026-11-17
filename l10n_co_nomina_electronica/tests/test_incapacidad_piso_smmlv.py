# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-163: piso de 1 SMMLV por dia en la incapacidad comun (CST art. 227; T-468/2010).

valor por dia = max(valor_dia x pct del tramo, SMMLV / 30), en todos los tramos. 2026: SMMLV
1.750.905 -> piso diario 58.363,5; pct empleador y 3-90 = 66,67 %, 91+ = 50 %. Valores a mano:
- 1 SMMLV (valor dia 58.363,5): el 66,67 % queda por debajo del piso en todos los tramos (se paga
  el 100 %): 5 dias = 291.817,5; 100 dias = 100 x 58.363,5 = 5.836.350.
- 1,5 SMMLV = 2.626.357,5 (valor dia 87.545,25): 66,67 % = 58.366,418175 (> piso) y 50 % =
  43.772,625 (< piso): 5 dias = 291.832,090875; 100 dias = 90 x 58.366,418175 + 10 x 58.363,5
  = 5.836.612,63575.
- 3.000.000 (> 1,5 SMMLV): 100.000/dia: 66,67 % = 66.670 y 50 % = 50.000 (< piso 58.363,5):
  5 dias = 333.350; 100 dias = 90 x 66.670 + 10 x 58.363,5 = 6.000.300 + 583.635 = 6.583.935.
No cambian la incapacidad laboral ni las licencias."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

SMMLV_2026 = 1750905.0


@tagged('post_install', '-at_install')
class TestIncapacidadPisoSmmlv(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Piso SMMLV'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Piso SMMLV', 'country_id': cls.env.ref('base.co').id})
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _recibo(self, name, wage):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': wage, 'date_start': date(2024, 3, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.nomina.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})

    def _pago(self, wage, dias, nombre='Piso'):
        return self._recibo(nombre, wage)._ne_pago_ausencia_calendario('CO_INC_COMUN', dias)

    def test_un_smmlv_se_paga_el_100_por_ciento_en_todos_los_tramos(self):
        self.assertAlmostEqual(self._pago(SMMLV_2026, 2), 2 * 58363.5, delta=0.01)
        self.assertAlmostEqual(self._pago(SMMLV_2026, 5), 291817.5, delta=0.01)
        self.assertAlmostEqual(self._pago(SMMLV_2026, 100), 5836350.0, delta=0.01)

    def test_uno_y_medio_smmlv_el_piso_solo_rige_donde_el_pct_queda_por_debajo(self):
        wage = 1.5 * SMMLV_2026  # 2.626.357,5
        self.assertAlmostEqual(self._pago(wage, 5), 291832.09, delta=0.01)
        self.assertAlmostEqual(self._pago(wage, 100), 5836612.64, delta=0.01)

    def test_tres_smmlv_o_mas_el_porcentaje_domina_salvo_el_tramo_del_50(self):
        self.assertAlmostEqual(self._pago(3000000.0, 5), 333350.0, delta=0.01)
        self.assertAlmostEqual(self._pago(3000000.0, 100), 6583935.0, delta=0.01)

    def test_incapacidad_laboral_y_licencias_no_tienen_piso(self):
        slip = self._recibo('SinPiso', SMMLV_2026)
        self.assertAlmostEqual(
            slip._ne_pago_ausencia_calendario('CO_INC_LABORAL', 5), 5 * 58363.5, delta=0.01)
        self.assertAlmostEqual(
            slip._ne_pago_ausencia_calendario('CO_LIC_MAT', 10), 10 * 58363.5, delta=0.01)
