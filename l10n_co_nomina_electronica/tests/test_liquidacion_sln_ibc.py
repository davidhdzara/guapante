# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-168: IBC de la liquidacion con licencia no remunerada (SLN) del ultimo tramo.

Antes la estructura de liquidacion no tenia CO_IBC_SLN y su CO_IBC_SP no sumaba los dias SLN
(la nomina general si). Valores a mano: contrato $3.000.000 desde 2026-01-01 (valor dia 100.000),
retiro 2026-08-15, licencia no remunerada lun 3 a vie 7 de agosto (5 dias habiles):
- tramo 1-15 de agosto = 15 dias; SLN 5 -> CO_LIQ_SALARIOS = 10 dias = 1.000.000.
- Sin historial de nomina general, el ultimo IBC anterior es el salario (3.000.000):
  CO_IBC_SLN = 3.000.000 / 30 x 5 = 500.000.
- CO_IBC_SP = salarial 1.000.000 + SLN 500.000 = 1.500.000 (piso 1 SMMLV x 15/30 = 875.452,5 no aplica).
- Descuentos salud y pension: 4 % de (1.500.000 - 500.000) = 40.000 c/u (en SLN el trabajador no
  paga su cuota ni nadie la asume).
- Con una nomina general previa (julio) de IBC 2.400.000: CO_IBC_SLN = 2.400.000 / 30 x 5 = 400.000;
  CO_IBC_SP = 1.400.000; descuentos 40.000."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

RETIRO = date(2026, 8, 15)


@tagged('post_install', '-at_install')
class TestLiquidacionSlnIbc(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'name': 'Compañía de Prueba IBC SLN Liquidación'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura SLN', 'country_id': cls.env.ref('base.co').id})
        cls.liquidacion = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.leave_type_lic_nr = cls.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_lic_nr')

    def _contrato(self, name):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2026, 1, 1), 'state': 'open'})
        contract.generate_work_entries(date(2026, 1, 1), RETIRO)
        return employee, contract

    def _licencia(self, employee, desde, hasta):
        leave = self.env['hr.leave'].create({
            'employee_id': employee.id, 'holiday_status_id': self.leave_type_lic_nr.id,
            'request_date_from': desde, 'request_date_to': hasta})
        leave.action_validate()
        self.assertEqual(leave.state, 'validate')

    def _liquidacion(self, employee, contract):
        slip = self.env['hr.payslip'].create({
            'name': 'Liquidación %s' % employee.name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.liquidacion.id,
            'date_from': contract.date_start, 'date_to': RETIRO})
        slip.compute_sheet()
        return slip

    def _total(self, slip, code):
        return sum(slip.line_ids.filtered(lambda l: l.code == code).mapped('total'))

    def test_sln_del_tramo_suma_al_ibc_y_no_se_descuenta_al_trabajador(self):
        employee, contract = self._contrato('SlnTramo')
        self._licencia(employee, date(2026, 8, 3), date(2026, 8, 7))
        slip = self._liquidacion(employee, contract)
        salarios = slip.line_ids.filtered(lambda l: l.code == 'CO_LIQ_SALARIOS')
        self.assertEqual((salarios.quantity, salarios.total), (10.0, 1000000.0))
        self.assertAlmostEqual(self._total(slip, 'CO_IBC_SALARIAL'), 1000000.0, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_IBC_SLN'), 500000.0, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_IBC_SP'), 1500000.0, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_LIQ_SALUD'), -40000.0, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_LIQ_PENSION'), -40000.0, delta=0.01)

    def test_la_base_sln_es_el_ultimo_ibc_de_la_nomina_general_anterior(self):
        employee, contract = self._contrato('SlnHistorial')
        previa = self.env['hr.payslip'].create({
            'name': 'Nómina julio', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': self.nomina.id,
            'date_from': date(2026, 7, 1), 'date_to': date(2026, 7, 31)})
        regla = self.env['hr.salary.rule'].search(
            [('code', '=', 'CO_SS_BASE_IBC'), ('struct_id', '=', self.nomina.id)], limit=1)
        self.assertTrue(regla)
        self.env['hr.payslip.line'].create({
            'slip_id': previa.id, 'salary_rule_id': regla.id, 'code': 'CO_SS_BASE_IBC',
            'name': 'IBC base', 'contract_id': contract.id, 'employee_id': employee.id,
            'quantity': 1.0, 'rate': 100.0, 'amount': 2400000.0, 'total': 2400000.0})
        previa.state = 'done'
        self._licencia(employee, date(2026, 8, 3), date(2026, 8, 7))
        slip = self._liquidacion(employee, contract)
        self.assertAlmostEqual(self._total(slip, 'CO_IBC_SLN'), 400000.0, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_IBC_SP'), 1400000.0, delta=0.01)
        self.assertAlmostEqual(self._total(slip, 'CO_LIQ_SALUD'), -40000.0, delta=0.01)

    def test_sln_de_un_mes_anterior_no_cuenta(self):
        employee, contract = self._contrato('SlnMayo')
        self._licencia(employee, date(2026, 5, 4), date(2026, 5, 8))
        slip = self._liquidacion(employee, contract)
        self.assertEqual(self._total(slip, 'CO_IBC_SLN'), 0.0)
        self.assertAlmostEqual(self._total(slip, 'CO_IBC_SP'), 1500000.0, delta=0.01)  # 15 dias
        self.assertAlmostEqual(self._total(slip, 'CO_LIQ_SALUD'), -60000.0, delta=0.01)

    def test_el_consolidado_mensual_recibe_la_base_sln_de_la_liquidacion(self):
        employee, contract = self._contrato('SlnConsolidado')
        self._licencia(employee, date(2026, 8, 3), date(2026, 8, 7))
        slip = self._liquidacion(employee, contract)
        slip.state = 'done'
        consolidado = self.env['l10n.co.ibc.mensual']._refrescar(self.company, employee, RETIRO)
        self.assertAlmostEqual(consolidado.ibc_sln, 500000.0, delta=0.01)
        self.assertAlmostEqual(consolidado.ibc_sp, 1500000.0, delta=0.01)
        self.assertEqual(consolidado.dias_sln, 5)
