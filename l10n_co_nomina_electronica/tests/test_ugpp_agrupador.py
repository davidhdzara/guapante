# -*- coding: utf-8 -*-
"""Frente 4, U4 (doc 57 §9): una fila por empleado y mes; el mes es el del periodo trabajado (``date_to``) y el VALOR de
las vacaciones va en el mes en que se pagó (Guía UGPP V-20.1, numeral 1.3, p. 13). Nivel de verificación: se prueba la
agrupación (valores y filas); el Excel completo con recibos calculados lo cubre test_ugpp_dias."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestUgppAgrupador(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Agrupador UGPP', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_ne_fuente_fecha_pago': 'recibo'})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Tipo Agrupador', 'country_id': cls.env.ref('base.co').id})
        cls.estructura = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        categoria = cls.env['hr.salary.rule.category'].search([], limit=1)
        Regla = cls.env['hr.salary.rule']
        base = {'category_id': categoria.id, 'struct_id': cls.estructura.id, 'amount_select': 'fix', 'amount_fix': 0.0}
        cls.salario = Regla.create({**base, 'name': 'Salario Agr', 'code': 'AGR_SAL',
                                    'l10n_co_ugpp_payment_type': 'tp_salarial'})
        cls.vacaciones = Regla.create({**base, 'name': 'Vacaciones Agr', 'code': 'AGR_VAC',
                                       'l10n_co_ugpp_payment_type': 'tp_vacaciones'})
        cls.vac_terminacion = Regla.create({**base, 'name': 'Vacaciones terminación Agr', 'code': 'AGR_VACT',
                                            'l10n_co_ugpp_payment_type': 'tp_vacaciones_terminacion'})
        cls.empleado = cls.env['hr.employee'].create({
            'name': 'Empleado Agrupador', 'company_id': cls.company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        cls.contrato = cls.env['hr.contract'].create({
            'name': 'Contrato Agrupador', 'employee_id': cls.empleado.id, 'company_id': cls.company.id,
            'structure_type_id': cls.tipo.id, 'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open',
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00'})
        cls.septiembre = cls._reporte(9, date(2026, 9, 1), date(2026, 9, 30))
        cls.octubre = cls._reporte(10, date(2026, 10, 1), date(2026, 10, 31))

    @classmethod
    def _reporte(cls, mes, desde, hasta):
        return cls.env['l10n_co_nomina.ugpp'].create({
            'year': 2026, 'month': str(mes), 'date_from': desde, 'date_to': hasta, 'company_id': cls.company.id})

    def _recibo(self, nombre, ini, fin, pagado, *valores):
        recibo = self.env['hr.payslip'].create({
            'name': nombre, 'employee_id': self.empleado.id, 'contract_id': self.contrato.id,
            'company_id': self.company.id, 'struct_id': self.estructura.id, 'date_from': ini, 'date_to': fin})
        for regla, total in valores:
            self.env['hr.payslip.line'].create({
                'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': regla.code, 'name': regla.name,
                'category_id': regla.category_id.id, 'employee_id': self.empleado.id,
                'contract_id': self.contrato.id, 'total': total, 'amount': total, 'quantity': 1, 'rate': 100})
        recibo.write({'state': 'done', 'paid_date': pagado})
        return recibo

    def _valores(self, reporte):
        recibos = reporte._ugpp_recibos()
        return recibos, reporte._ugpp_valores(recibos).get(self.empleado.id, {})

    def test_a_vacaciones_pagadas_en_otro_mes_van_en_el_mes_del_pago(self):
        r1 = self._recibo('R1 quincena', date(2026, 9, 16), date(2026, 9, 30), date(2026, 9, 30), (self.salario, 1000.0))
        r2 = self._recibo('R2 vacaciones', date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 5),
                          (self.vacaciones, 500.0))
        recibos, valores = self._valores(self.septiembre)
        self.assertEqual(recibos, r1 | r2)
        self.assertEqual(valores, {self.salario.id: 1000.0})             # sin las vacaciones pagadas en octubre
        recibos, valores = self._valores(self.octubre)
        self.assertEqual(recibos, r2)                                    # sin recibos de octubre: solo las vacaciones
        self.assertEqual(valores, {self.vacaciones.id: 500.0})
        self.assertEqual(self.octubre._ugpp_empleados(recibos), [(self.empleado, r2)])
        self.assertFalse(self.octubre._ugpp_recibos_del_mes(recibos))    # sin días ni novedades en esa fila

    def test_b_vacaciones_pagadas_en_el_mismo_mes_van_juntas(self):
        self._recibo('R1', date(2026, 9, 16), date(2026, 9, 30), date(2026, 9, 30), (self.salario, 1000.0))
        self._recibo('R2', date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 30), (self.vacaciones, 500.0))
        _recibos, valores = self._valores(self.septiembre)
        self.assertEqual(valores, {self.salario.id: 1000.0, self.vacaciones.id: 500.0})

    def test_c_con_recibo_de_octubre_las_vacaciones_van_en_la_misma_fila(self):
        self._recibo('R2', date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 5), (self.vacaciones, 500.0))
        r3 = self._recibo('R3', date(2026, 10, 1), date(2026, 10, 15), date(2026, 10, 15), (self.salario, 700.0))
        recibos, valores = self._valores(self.octubre)
        self.assertEqual(valores, {self.salario.id: 700.0, self.vacaciones.id: 500.0})
        filas = self.octubre._ugpp_empleados(recibos)
        self.assertEqual(filas, [(self.empleado, r3)])                   # una sola fila por empleado y mes
        self.assertEqual(self.octubre._ugpp_recibos_del_mes(recibos), r3)

    def test_d_vacaciones_sin_fecha_de_pago_es_error_que_nombra_el_recibo(self):
        self._recibo('R2 sin pago', date(2026, 9, 1), date(2026, 9, 30), False, (self.vacaciones, 500.0))
        with self.assertRaisesRegex(UserError, 'R2 sin pago[\s\S]*fecha de pago en ese recibo'):
            self.octubre._ugpp_recibos()

    def test_e_dos_quincenas_suman_en_una_sola_fila(self):
        r1 = self._recibo('Q1', date(2026, 9, 1), date(2026, 9, 15), date(2026, 9, 15), (self.salario, 1000.0))
        r2 = self._recibo('Q2', date(2026, 9, 16), date(2026, 9, 30), date(2026, 9, 30), (self.salario, 1200.0))
        recibos, valores = self._valores(self.septiembre)
        self.assertEqual(valores, {self.salario.id: 2200.0})
        self.assertEqual(len(self.septiembre._ugpp_empleados(recibos)), 1)
        self.assertEqual(self.septiembre._ugpp_empleados(recibos)[0][1], r2)   # referencia: el último recibo del mes
        self.assertEqual(recibos, r1 | r2)

    def test_f_vacaciones_por_terminacion_tambien_van_por_fecha_de_pago(self):
        self._recibo('Liquidación', date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 3),
                     (self.salario, 900.0), (self.vac_terminacion, 300.0))
        _r, sept = self._valores(self.septiembre)
        _r, octu = self._valores(self.octubre)
        self.assertEqual(sept, {self.salario.id: 900.0})
        self.assertEqual(octu, {self.vac_terminacion.id: 300.0})

    def test_un_recibo_de_otro_mes_sin_vacaciones_no_entra(self):
        self._recibo('Agosto', date(2026, 8, 1), date(2026, 8, 31), date(2026, 8, 31), (self.salario, 800.0))
        self.assertFalse(self.septiembre._ugpp_recibos())

    def test_las_reglas_del_reporte_salen_del_valor_efectivo_del_mes(self):
        # las vacaciones del recibo de septiembre se pagan en octubre: en septiembre no es un concepto del reporte
        self._recibo('R1', date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 5),
                     (self.salario, 1000.0), (self.vacaciones, 500.0))
        recibos = self.septiembre._ugpp_recibos()
        self.assertEqual(self.septiembre._get_ugpp_salary_rules(recibos), self.salario)
        self.assertEqual(self.octubre._get_ugpp_salary_rules(self.octubre._ugpp_recibos()), self.vacaciones)
