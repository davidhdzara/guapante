# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""El cambio del 15 de julio de 2026 (Ley 2101/2021) y del 1 de julio (Ley 2466/2025) sale de
hr.rule.parameter "como parametros", no del codigo.

Parametros (data/l10n_co_rule_parameters_data.xml), con fecha:
- l10n_co_horas_mensuales (divisor): 230 desde 2024-07-15, 220 desde 2025-07-15, 210 desde 2026-07-15.
- l10n_co_factor_hrddf (recargo dominical/festivo diurno): 1,80 desde 2025-07-01, 1,90 desde 2026-07-01.
Las reglas de horas extra resuelven ambos con payslip.date_from.

Valores a mano con salario 2.310.000: valor hora = 2.310.000 / 220 = 10.500 y / 210 = 11.000.
HED 4 h al factor 1,25; HRDDF 6 h:
- Quincena 16-30 jun (date_from 16-jun): divisor 220, factor 1,80 -> HED 10.500 x 1,25 x 4 = 52.500;
  HRDDF 10.500 x 1,80 x 6 = 113.400.
- Quincena 1-15 jul (date_from 1-jul): divisor 220, factor 1,90 -> HED 52.500; HRDDF 10.500 x 1,90 x 6 = 119.700.
- Quincena 16-31 jul (date_from 16-jul): divisor 210, factor 1,90 -> HED 11.000 x 1,25 x 4 = 55.000;
  HRDDF 11.000 x 1,90 x 6 = 125.400.

LIMITACION DOCUMENTADA (no se programa): la regla usa la fecha de INICIO del recibo. Una
quincena 1-15 de julio queda completa con divisor 220, incluidas las horas del dia 15, aunque
desde el 15 de julio el parametro ya sea 210. La diferencia de un solo dia se acepta (decision
de David: "como parametros").
"""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

WAGE = 2310000.0


@tagged('post_install', '-at_install')
class TestJornada15Julio(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Jornada 15 de Julio'})
        structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Jornada', 'country_id': cls.env.ref('base.co').id})
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Empleado Jornada', 'company_id': cls.company.id,
            'l10n_co_ne_payment_method': '10'})
        cls.contract = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Jornada', 'employee_id': employee.id,
            'company_id': cls.company.id, 'structure_type_id': structure_type.id,
            'wage': WAGE, 'date_start': date(2024, 3, 1), 'state': 'open'})
        cls.employee = employee

    def _quincena(self, date_from, date_to):
        slip = self.env['hr.payslip'].create({
            'name': 'Quincena %s' % date_from, 'employee_id': self.employee.id,
            'contract_id': self.contract.id, 'company_id': self.company.id,
            'struct_id': self.nomina.id, 'date_from': date_from, 'date_to': date_to})
        for xmlid, code, horas in (
                ('input_co_hed', 'CO_HED', 4.0), ('input_co_hrddf', 'CO_HRDDF', 6.0)):
            self.env['hr.payslip.input'].create({
                'payslip_id': slip.id, 'code': code, 'amount': horas,
                'input_type_id': self.env.ref('l10n_co_nomina_electronica.%s' % xmlid).id})
        slip.compute_sheet()
        return slip

    def _total(self, slip, code):
        linea = slip.line_ids.filtered(lambda l: l.code == code)
        self.assertTrue(linea, 'La regla %s no generó línea.' % code)
        return linea.total

    def test_parametros_con_fecha_de_corte_exacta(self):
        slip = self._quincena(date(2026, 7, 1), date(2026, 7, 15))
        horas = lambda d: slip._rule_parameter('l10n_co_horas_mensuales', d)  # noqa: E731
        factor = lambda d: slip._rule_parameter('l10n_co_factor_hrddf', d)  # noqa: E731
        self.assertEqual(horas(date(2026, 7, 14)), 220)
        self.assertEqual(horas(date(2026, 7, 15)), 210)
        self.assertEqual(factor(date(2026, 6, 30)), 1.80)
        self.assertEqual(factor(date(2026, 7, 1)), 1.90)

    def test_quincena_16_a_30_de_junio_divisor_220_y_recargo_dominical_1_80(self):
        slip = self._quincena(date(2026, 6, 16), date(2026, 6, 30))
        self.assertAlmostEqual(self._total(slip, 'CO_HED'), 52500.0, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_HRDDF'), 113400.0, delta=0.01)

    def test_quincena_1_a_15_de_julio_divisor_220_y_recargo_dominical_1_90(self):
        slip = self._quincena(date(2026, 7, 1), date(2026, 7, 15))
        self.assertAlmostEqual(self._total(slip, 'CO_HED'), 52500.0, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_HRDDF'), 119700.0, delta=0.01)

    def test_quincena_16_a_31_de_julio_divisor_210_y_recargo_dominical_1_90(self):
        slip = self._quincena(date(2026, 7, 16), date(2026, 7, 31))
        self.assertAlmostEqual(self._total(slip, 'CO_HED'), 55000.0, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_HRDDF'), 125400.0, delta=0.01)

    def test_limitacion_documentada_el_dia_15_de_la_primera_quincena_queda_con_220(self):
        """No se programa: la quincena 1-15 de julio usa la fecha de inicio (220) para todas sus
        horas; si las horas fueran del 15 con el parametro del dia (210) valdrian 11.000 por hora
        en vez de 10.500."""
        slip = self._quincena(date(2026, 7, 1), date(2026, 7, 15))
        valor_hora_aplicado = self._total(slip, 'CO_HED') / (4.0 * 1.25)
        self.assertAlmostEqual(valor_hora_aplicado, WAGE / 220, delta=0.01)
        self.assertNotAlmostEqual(valor_hora_aplicado, WAGE / 210, delta=0.01)
