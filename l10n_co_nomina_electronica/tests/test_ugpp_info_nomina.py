# -*- coding: utf-8 -*-
"""Frente 4, U7 (doc 57 §11.5): "Información módulo de nómina" (Res. 858 de 2021, art. 2.3.7). Una fila por empleado y
concepto con valor, del mismo agrupador de la hoja nómina; cuenta de débito primero (la norma no distingue gasto de
pasivo: validar en el piloto)."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestUgppInfoNomina(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa 237 UGPP', 'country_id': cls.env.ref('base.co').id, 'vat': '900123456-8',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_ne_fuente_fecha_pago': 'recibo'})
        Cuenta = cls.env['account.account'].with_company(cls.company)
        cls.gasto = Cuenta.create({'code': '510506', 'name': 'Sueldos 237', 'account_type': 'expense'})
        cls.por_pagar = Cuenta.create({'code': '250505', 'name': 'Por pagar 237', 'account_type': 'liability_current'})
        cls.estructura = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        base = {'category_id': cls.env['hr.salary.rule.category'].search([], limit=1).id,
                'struct_id': cls.estructura.id, 'amount_select': 'fix', 'amount_fix': 0.0}
        Regla = cls.env['hr.salary.rule']
        # El número de concepto sigue el orden (sequence, code) de las reglas del reporte: se fija ``sequence`` para
        # que Salario sea el concepto 1 y Prima el 2 (sin ``sequence`` empataba y desempataba el código: Prima < Salario).
        cls.salario = Regla.create({**base, 'name': 'Salario 237', 'code': 'I237_SAL', 'sequence': 10,
                                    'l10n_co_ugpp_payment_type': 'tp_salarial'})
        cls.prima = Regla.create({**base, 'name': 'Prima 237', 'code': 'I237_PRI', 'sequence': 20,
                                  'l10n_co_ugpp_payment_type': 'tp_prestaciones'})
        cls.salario.with_company(cls.company).write({'account_debit': cls.gasto.id, 'account_credit': cls.por_pagar.id})
        cls.prima.with_company(cls.company).write({'account_credit': cls.por_pagar.id})      # solo crédito
        tipo = cls.env['hr.payroll.structure.type'].create({'name': 'Tipo 237', 'country_id': cls.env.ref('base.co').id})
        cls.empleado = cls.env['hr.employee'].create({
            'name': 'Empleado 237', 'company_id': cls.company.id, 'identification_id': '1020304050',
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        cls.contrato = cls.env['hr.contract'].create({
            'name': 'Contrato 237', 'employee_id': cls.empleado.id, 'company_id': cls.company.id,
            'structure_type_id': tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00'})
        cls.reporte = cls.env['l10n_co_nomina.ugpp'].create({
            'year': 2026, 'month': '9', 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30),
            'company_id': cls.company.id})

    def _recibo(self, *valores):
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo 237', 'employee_id': self.empleado.id, 'contract_id': self.contrato.id,
            'company_id': self.company.id, 'struct_id': self.estructura.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        for regla, total in valores:
            self.env['hr.payslip.line'].create({
                'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': regla.code, 'name': regla.name,
                'category_id': regla.category_id.id, 'employee_id': self.empleado.id,
                'contract_id': self.contrato.id, 'total': total, 'amount': total, 'quantity': 1, 'rate': 100})
        recibo.write({'state': 'done', 'paid_date': date(2026, 9, 30)})
        return recibo

    def test_una_fila_por_empleado_y_concepto_con_las_nueve_columnas_de_la_norma(self):
        recibo = self._recibo((self.salario, 1000.5), (self.prima, 500.0))
        filas = self.reporte._ugpp_filas_info_nomina(recibo)
        self.assertEqual(len(filas), 2)
        # cuenta, nombre de cuenta, código concepto, nombre concepto, documento, nombre trabajador, año, mes, valor
        self.assertIn([510506, 'Sueldos 237', 1, 'Salario 237', 1020304050, 'Empleado 237', 2026, 9, 1001], filas)
        self.assertIn([250505, 'Por pagar 237', 2, 'Prima 237', 1020304050, 'Empleado 237', 2026, 9, 500], filas)

    def test_cuenta_de_debito_primero_y_credito_solo_si_no_hay_debito(self):
        recibo = self._recibo((self.salario, 100.0), (self.prima, 100.0))
        cuentas = {fila[3]: fila[0] for fila in self.reporte._ugpp_filas_info_nomina(recibo)}
        self.assertEqual(cuentas, {'Salario 237': 510506, 'Prima 237': 250505})

    def test_el_codigo_del_concepto_es_el_mismo_de_la_hoja_nomina(self):
        recibo = self._recibo((self.salario, 100.0), (self.prima, 100.0))
        reglas = self.reporte._get_ugpp_salary_rules(recibo)
        codigos = {fila[3]: fila[2] for fila in self.reporte._ugpp_filas_info_nomina(recibo)}
        self.assertEqual(codigos, {regla.name: i for i, regla in enumerate(reglas, 1)})

    def test_un_concepto_en_cero_no_genera_fila(self):
        recibo = self._recibo((self.salario, 100.0), (self.prima, 0.0))
        self.assertEqual([f[3] for f in self.reporte._ugpp_filas_info_nomina(recibo)], ['Salario 237'])

    def test_regla_con_valor_y_sin_cuenta_falla_nombrandola(self):
        sin_cuenta = self.env['hr.salary.rule'].create({
            'name': 'Sin cuenta 237', 'code': 'I237_NO', 'category_id': self.salario.category_id.id,
            'struct_id': self.estructura.id, 'amount_select': 'fix', 'amount_fix': 0.0,
            'l10n_co_ugpp_payment_type': 'tp_salarial'})
        recibo = self._recibo((self.salario, 100.0), (sin_cuenta, 50.0))
        with self.assertRaisesRegex(UserError, 'Sin cuenta 237'):
            self.reporte._ugpp_filas_info_nomina(recibo)

    def test_el_boton_genera_el_excel(self):
        self._recibo((self.salario, 100.0))
        accion = self.reporte.action_generar_info_nomina()
        self.assertEqual(accion['type'], 'ir.actions.act_url')
        self.assertTrue(self.reporte.info_nomina_file)
        self.assertIn('Informacion_modulo_nomina_900123456_9_2026', self.reporte.info_nomina_filename)
