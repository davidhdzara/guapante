# -*- coding: utf-8 -*-
"""CO_LIQ_VACACIONES descuenta las vacaciones ya disfrutadas o compensadas.

Dias causados = dias de prestacion de servicio x 30 / 720 (15 por cada 360; dias reales, febrero
28/29 y el 31 no cuenta, modo 'real'). Los valores esperados se calculan a mano: con ingreso
2025-01-01 y retiro 2026-01-02 son 367 reales - 7 treintaiunos = 360 dias = 15 dias causados; salario $3.000.000 => valor dia $100.000. Las ausencias (hr.leave -> work entries)
se simulan con mock sobre _ne_ausencia_habil: aqui se prueba el descuento, no la conversion
nativa de ausencias (ya cubierta en test_ausencias_nomina).
"""

from datetime import date
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

INGRESO = date(2025, 1, 1)
RETIRO = date(2026, 1, 2)  # 360 dias de servicio (367 reales - 7 treintaiunos), inclusivo
VALOR_DIA = 100000.0


@tagged('post_install', '-at_install')
class TestLiquidacionVacaciones(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 
            'name': 'Compañía de Prueba Vacaciones Liquidación'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Vacaciones', 'country_id': cls.env.ref('base.co').id})
        cls.liquidacion = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.input_vac = cls.env.ref('l10n_co_nomina_electronica.input_co_vac')
        cls.regla_vac_comp = cls.env.ref(
            'l10n_co_nomina_electronica.hr_salary_rule_co_vacaciones_compensadas')

    def _contrato(self, name, date_start=INGRESO):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 3000000.0, 'date_start': date_start, 'state': 'open'})
        return employee, contract

    def _liquidacion(self, employee, contract, date_to=RETIRO):
        """Como lo crea el asistente: date_from = inicio de contrato."""
        return self.env['hr.payslip'].create({
            'name': 'Liquidación %s' % employee.name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.liquidacion.id,
            'date_from': contract.date_start, 'date_to': date_to})

    def _previo(self, employee, contract, state='done', dias_input=0.0, monto_comp=0.0):
        slip = self.env['hr.payslip'].create({
            'name': 'Nómina previa', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': self.nomina.id,
            'date_from': date(2025, 6, 1), 'date_to': date(2025, 6, 30)})
        if dias_input:
            self.env['hr.payslip.input'].create({
                'payslip_id': slip.id, 'input_type_id': self.input_vac.id,
                'code': 'CO_VAC', 'amount': dias_input})
        if monto_comp:
            self.env['hr.payslip.line'].create({
                'slip_id': slip.id, 'salary_rule_id': self.regla_vac_comp.id,
                'code': 'CO_VAC_COMP', 'name': 'Vacaciones compensadas',
                'contract_id': contract.id, 'employee_id': employee.id,
                'quantity': 1.0, 'rate': 100.0, 'amount': monto_comp, 'total': monto_comp})
        slip.state = state
        return slip

    def _calcular(self, slip, dias_ausencia=0):
        with mock.patch.object(type(slip), '_ne_ausencia_habil',
                               return_value=(dias_ausencia, [])):
            slip.compute_sheet()
            return slip._ne_liq_vacaciones_dias()

    def _linea(self, slip):
        linea = slip.line_ids.filtered(lambda l: l.code == 'CO_LIQ_VACACIONES')
        self.assertTrue(linea, 'CO_LIQ_VACACIONES no generó línea.')
        return linea

    def test_sin_vacaciones_tomadas_paga_los_15_dias_causados(self):
        employee, contract = self._contrato('SinVac')
        slip = self._liquidacion(employee, contract)
        dias = self._calcular(slip)
        self.assertAlmostEqual(dias['causados'], 15.0, places=6)
        self.assertAlmostEqual(dias['pendientes'], 15.0, places=6)
        linea = self._linea(slip)
        self.assertAlmostEqual(linea.total, 15 * VALOR_DIA, delta=0.01)
        # La Cantidad de la linea (la que lee el XML) son los dias pendientes.
        self.assertAlmostEqual(linea.quantity, 15.0, places=6)
        self.assertAlmostEqual(linea.amount, VALOR_DIA, delta=0.01)

    def test_ausencia_de_vacaciones_validada_descuenta_sus_dias_habiles(self):
        employee, contract = self._contrato('ConAusencia')
        slip = self._liquidacion(employee, contract)
        dias = self._calcular(slip, dias_ausencia=5)
        self.assertAlmostEqual(dias['pendientes'], 10.0, places=6)
        self.assertAlmostEqual(self._linea(slip).total, 10 * VALOR_DIA, delta=0.01)

    def test_input_co_vac_de_recibo_confirmado_descuenta_sus_dias(self):
        employee, contract = self._contrato('ConInput')
        self._previo(employee, contract, dias_input=3.0)
        slip = self._liquidacion(employee, contract)
        dias = self._calcular(slip)
        self.assertAlmostEqual(dias['disfrutados'], 3.0, places=6)
        self.assertAlmostEqual(self._linea(slip).total, 12 * VALOR_DIA, delta=0.01)

    def test_vacaciones_compensadas_en_dinero_descuentan_monto_sobre_valor_dia(self):
        employee, contract = self._contrato('ConCompensadas')
        self._previo(employee, contract, monto_comp=300000.0)
        slip = self._liquidacion(employee, contract)
        dias = self._calcular(slip)
        self.assertAlmostEqual(dias['compensados'], 3.0, places=6)
        self.assertAlmostEqual(self._linea(slip).total, 12 * VALOR_DIA, delta=0.01)

    def test_quien_tomo_mas_de_lo_causado_no_genera_valor_negativo(self):
        employee, contract = self._contrato('Exceso')
        slip = self._liquidacion(employee, contract)
        dias = self._calcular(slip, dias_ausencia=20)
        self.assertEqual(dias['pendientes'], 0.0)
        self.assertEqual(self._linea(slip).total, 0.0)

    def test_recibo_previo_sin_confirmar_no_cuenta(self):
        employee, contract = self._contrato('PrevioBorrador')
        self._previo(employee, contract, state='draft', dias_input=3.0, monto_comp=300000.0)
        slip = self._liquidacion(employee, contract)
        dias = self._calcular(slip)
        self.assertEqual(dias['disfrutados'], 0.0)
        self.assertEqual(dias['compensados'], 0.0)
        self.assertAlmostEqual(dias['pendientes'], 15.0, places=6)

    def test_contrato_corto_causa_dias_proporcionales(self):
        """88 dias de servicio (90 reales - el 31-ene y el 31-mar) -> 88 x 30 / 720 = 3,666667 dias."""
        employee, contract = self._contrato('Corto', date_start=date(2025, 1, 1))
        slip = self._liquidacion(employee, contract, date_to=date(2025, 3, 31))
        dias = self._calcular(slip)
        self.assertAlmostEqual(dias['causados'], 88 * 30 / 720.0, places=6)
        self.assertAlmostEqual(self._linea(slip).total, 88 * 30 / 720.0 * VALOR_DIA, delta=0.01)
