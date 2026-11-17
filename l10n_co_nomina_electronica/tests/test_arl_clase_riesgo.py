# -*- coding: utf-8 -*-
"""H-005 (2026-11-09, PM -> developer): CO_ARL_CIA aplica la tarifa ARL de la Clase de Riesgo del
contrato (l10n_co_pila_clase_riesgo), no siempre la Clase I.

Tarifas (Decreto 768/2022 clasificación; Art. 2.2.4.3.5 Decreto 1072/2015 tarifas):
I 0.522, II 1.044, III 2.436, IV 4.350, V 6.960 (%).

Nivel de verificación (doc 38): pruebas de la regla salarial con empleados de Clase I a V
sobre la estructura real; NO cubre el archivo PILA generado (ver docstring de la última prueba).
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

TARIFAS = {'1': 0.522, '2': 1.044, '3': 2.436, '4': 4.350, '5': 6.960}


@tagged('post_install', '-at_install')
class TestArlClaseRiesgo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba ARL Clase de Riesgo'})
        cls.env = cls.company.with_company(cls.company).env
        co = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura ARL', 'country_id': co.id,
        })
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _payslip(self, clase, wage=3000000.0):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado ARL Clase %s' % clase,
            'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato ARL %s' % clase,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'date_start': date(2024, 1, 1),
            'state': 'open',
            'l10n_co_pila_clase_riesgo': clase,
        })
        payslip = self.env['hr.payslip'].create({
            'name': 'Nómina ARL %s' % clase,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        return payslip

    def test_pct_arl_por_clase_lee_el_parametro_de_cada_clase(self):
        for clase, esperado in TARIFAS.items():
            payslip = self._payslip(clase)
            self.assertAlmostEqual(payslip._ne_pct_arl(), esperado, places=6, msg='Clase %s' % clase)

    def test_regla_co_arl_cia_aplica_la_tarifa_de_cada_clase(self):
        for clase, esperado in TARIFAS.items():
            payslip = self._payslip(clase)
            payslip.compute_sheet()
            linea = payslip.line_ids.filtered(lambda l: l.code == 'CO_ARL_CIA')
            self.assertTrue(linea, 'Falta la línea CO_ARL_CIA (Clase %s).' % clase)
            ibc = sum(
                l.total for l in payslip.line_ids if l.category_id.code == 'DEV_SAL')
            self.assertGreater(ibc, 0)
            self.assertAlmostEqual(
                linea.total, ibc * esperado / 100, delta=0.01, msg='Clase %s' % clase)

    def test_clase_i_no_cambia(self):
        """La tarifa de la Clase I sigue siendo la de l10n_co_pct_arl_default (0.522)."""
        payslip = self._payslip('1')
        self.assertAlmostEqual(
            payslip._ne_pct_arl(),
            payslip._rule_parameter('l10n_co_pct_arl_default', payslip.date_from), places=6)

    def test_clase_mayor_cuesta_mas_que_la_clase_menor(self):
        totales = {}
        for clase in ('1', '3', '5'):
            payslip = self._payslip(clase)
            payslip.compute_sheet()
            totales[clase] = payslip.line_ids.filtered(lambda l: l.code == 'CO_ARL_CIA').total
        self.assertLess(totales['1'], totales['3'])
        self.assertLess(totales['3'], totales['5'])

    def test_sin_clase_levanta_usererror_y_nombra_al_empleado(self):
        payslip = self._payslip('1')
        payslip.contract_id.l10n_co_pila_clase_riesgo = False
        payslip.company_id.l10n_co_pila_clase_riesgo = False  # .161: tampoco hay general
        with self.assertRaises(UserError) as exc:
            payslip._ne_pct_arl()
        self.assertIn(payslip.employee_id.name, str(exc.exception))
