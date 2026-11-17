# -*- coding: utf-8 -*-
"""Provisiones de prestaciones (CO_PROV_PRIMA / CO_PROV_CESANTIAS / CO_PROV_INT_CES / CO_PROV_VACACIONES) proporcionales al periodo (.279).

Defecto (QA, prenomina de abril de 2026 de Guapante, quincenal): las 4 reglas daban el valor MENSUAL completo en cada recibo; confirmar las
dos quincenas acumulaba el doble en el mes y en el asiento. Ahora cada regla multiplica su valor mensual por
``HrPayslip._ne_factor_provision_periodo()`` = ``_ne_dias_bajo_contrato()`` / ``l10n_co_dias_mes_comercial`` (opcion A del diseno, aprobada por
Tech Lead el 17-nov-2026): mes completo = 1 (igual que antes), quincena = 15/30, semana = 7/30, ingreso a mitad de mes recorta los dias. Las
ausencias NO descuentan la provision (no se usa ``_ne_dias_pagables()``: restaria tambien las remuneradas).

Valores a mano con sueldo 6.000.000 (> 2 SMMLV: sin auxilio de transporte): por mes, prima y cesantias 6.000.000 / 12 = 500.000 y vacaciones
6.000.000 x 30 / 720 = 250.000; por quincena, 250.000 y 125.000. Los intereses de cesantias = cesantias x l10n_co_pct_intereses_cesantias / 100.
Abril de 2026 tiene 30 dias, mayo 31 y febrero 28 (ultimo dia real = dia comercial 30). NO ejecutadas en Odoo.
"""

from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

_REGLAS = (
    ('CO_PROV_PRIMA', 'hr_salary_rule_co_prov_prima'),
    ('CO_PROV_CESANTIAS', 'hr_salary_rule_co_prov_cesantias'),
    ('CO_PROV_INT_CES', 'hr_salary_rule_co_prov_int_cesantias'),   # lee la linea de cesantias: va despues de ella
    ('CO_PROV_VACACIONES', 'hr_salary_rule_co_prov_vacaciones'),
)
_SUELDO = 6000000.0
_MENSUAL_SUELDO = {'CO_PROV_PRIMA': 500000.0, 'CO_PROV_CESANTIAS': 500000.0, 'CO_PROV_VACACIONES': 250000.0}


@tagged('post_install', '-at_install')
class TestProvisionesPeriodo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Provisiones'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Provisiones', 'country_id': cls.env.ref('base.co').id})
        cls.tipo_semanal = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Provisiones Semanal', 'country_id': cls.env.ref('base.co').id,
            'default_schedule_pay': 'weekly'})
        ref = cls.env.ref
        cls.est_general = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.est_liquidacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.est_prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.est_bonificacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion')

    # ── ayudas ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _recibo(self, date_from, date_to, wage=_SUELDO, inicio=date(2024, 1, 1), semanal=False, integral=False, name='Recibo'):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00',
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        valores = {'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato %s' % name, 'employee_id': employee.id, 'company_id': self.company.id,
            'structure_type_id': (self.tipo_semanal if semanal else self.structure_type).id, 'wage': wage,
            'date_start': inicio, 'state': 'open'}
        contract = self.env['hr.contract'].create(valores)
        if integral:
            contract.write({'l10n_co_ne_integral_salary': True})
        return self.env['hr.payslip'].create({
            'name': name, 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': self.est_general.id,
            'date_from': date_from, 'date_to': date_to})

    def _provisiones(self, recibo):
        """Valor de las 4 reglas para ``recibo`` calculado con el motor de reglas (``_compute_rule``), en el orden del motor: los
        intereses leen ``result_rules['CO_PROV_CESANTIAS']['total']`` ya calculado."""
        valores, resultados = {}, {}
        for codigo, xmlid in _REGLAS:
            regla = self.env.ref('l10n_co_nomina_electronica.%s' % xmlid)
            monto = regla._compute_rule({'payslip': recibo, 'contract': recibo.contract_id, 'result_rules': resultados})[0]
            valores[codigo] = monto
            resultados[codigo] = {'total': monto}
        return valores

    def _pct_intereses(self, recibo):
        return recibo._rule_parameter('l10n_co_pct_intereses_cesantias', recibo.date_from)

    def _esperado_6m(self, recibo, fraccion):
        """Provision esperada de un recibo con sueldo 6.000.000 que cubre ``fraccion`` del mes."""
        valores = {codigo: valor * fraccion for codigo, valor in _MENSUAL_SUELDO.items()}
        valores['CO_PROV_INT_CES'] = _MENSUAL_SUELDO['CO_PROV_CESANTIAS'] * self._pct_intereses(recibo) / 100 * fraccion
        return valores

    def _assert_provisiones(self, recibo, esperado):
        real = self._provisiones(recibo)
        for codigo, valor in esperado.items():
            self.assertAlmostEqual(real[codigo], valor, delta=0.005, msg='%s: %s' % (codigo, recibo.name))

    def _premisa_sin_auxilio(self, recibo):
        smmlv = recibo._rule_parameter('l10n_co_smmlv', recibo.date_from)
        self.assertGreater(recibo.contract_id.wage, 2 * smmlv, 'Premisa: con este sueldo no hay auxilio de transporte')

    # ── pruebas ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_mes_completo_da_el_mismo_valor_mensual_de_antes(self):
        """Abril 1 al 30: factor 30/30 = 1.0 exacto y las 4 provisiones valen lo mismo que antes (prima y cesantias 500.000, vacaciones 250.000)."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30))
        self._premisa_sin_auxilio(recibo)
        self.assertEqual(recibo._ne_factor_provision_periodo(), 1.0)
        self._assert_provisiones(recibo, self._esperado_6m(recibo, 1.0))

    def test_quincena_1_al_15_es_la_mitad_y_la_linea_del_recibo_la_guarda(self):
        """Recibo quincenal 1 al 15 de abril: 15/30 y las lineas guardadas por el motor (compute_sheet) valen la mitad: 250.000, 250.000 y 125.000."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15))
        self._premisa_sin_auxilio(recibo)
        self.assertAlmostEqual(recibo._ne_factor_provision_periodo(), 0.5)
        recibo.compute_sheet()
        esperado = self._esperado_6m(recibo, 0.5)
        for codigo, valor in esperado.items():
            linea = recibo.line_ids.filtered(lambda l, c=codigo: l.code == c)
            self.assertEqual(len(linea), 1, 'Falta la linea %s del recibo' % codigo)
            self.assertAlmostEqual(linea.total, valor, delta=0.01, msg=codigo)
        self.assertAlmostEqual(esperado['CO_PROV_PRIMA'], 250000.0, delta=0.005)
        self.assertAlmostEqual(esperado['CO_PROV_VACACIONES'], 125000.0, delta=0.005)

    def test_quincena_16_al_30_es_la_mitad(self):
        recibo = self._recibo(date(2026, 4, 16), date(2026, 4, 30))
        self.assertAlmostEqual(recibo._ne_factor_provision_periodo(), 0.5)
        self._assert_provisiones(recibo, self._esperado_6m(recibo, 0.5))

    def test_quincena_16_al_31_de_un_mes_de_31_dias_es_la_mitad(self):
        """El ultimo dia real de cualquier mes es el dia comercial 30: 16 al 31 de mayo = 30 - 16 + 1 = 15 dias, no 16."""
        recibo = self._recibo(date(2026, 5, 16), date(2026, 5, 31))
        self.assertAlmostEqual(recibo._ne_factor_provision_periodo(), 0.5)
        self._assert_provisiones(recibo, self._esperado_6m(recibo, 0.5))

    def test_febrero_completo_es_un_mes_y_su_segunda_quincena_la_mitad(self):
        """Febrero de 2026 (28 dias): 1 al 28 = 30 comerciales (factor 1.0 exacto) y 16 al 28 = 15."""
        mes = self._recibo(date(2026, 2, 1), date(2026, 2, 28), name='Febrero mes')
        quincena = self._recibo(date(2026, 2, 16), date(2026, 2, 28), name='Febrero quincena')
        self.assertEqual(mes._ne_factor_provision_periodo(), 1.0)
        self._assert_provisiones(mes, self._esperado_6m(mes, 1.0))
        self.assertAlmostEqual(quincena._ne_factor_provision_periodo(), 0.5)
        self._assert_provisiones(quincena, self._esperado_6m(quincena, 0.5))

    def test_dos_quincenas_suman_exactamente_el_mes(self):
        """Invariante contable: lo provisionado en las dos quincenas de abril = lo de un recibo mensual de abril, en las 4 reglas."""
        primera = self._provisiones(self._recibo(date(2026, 4, 1), date(2026, 4, 15), name='Q1'))
        segunda = self._provisiones(self._recibo(date(2026, 4, 16), date(2026, 4, 30), name='Q2'))
        mensual = self._provisiones(self._recibo(date(2026, 4, 1), date(2026, 4, 30), name='Mes'))
        for codigo, _xmlid in _REGLAS:
            self.assertAlmostEqual(primera[codigo] + segunda[codigo], mensual[codigo], delta=0.005, msg=codigo)

    def test_ingreso_a_mitad_de_mes_recorta_los_dias(self):
        """Contrato desde el 11-abr-2026: el mes cubre 20 dias (11 al 30), la quincena 1 al 15 solo 5 y la 16 al 30 los 15."""
        mes = self._recibo(date(2026, 4, 1), date(2026, 4, 30), inicio=date(2026, 4, 11), name='Ingreso mes')
        q1 = self._recibo(date(2026, 4, 1), date(2026, 4, 15), inicio=date(2026, 4, 11), name='Ingreso q1')
        q2 = self._recibo(date(2026, 4, 16), date(2026, 4, 30), inicio=date(2026, 4, 11), name='Ingreso q2')
        self.assertAlmostEqual(mes._ne_factor_provision_periodo(), 20 / 30.0)
        self.assertAlmostEqual(q1._ne_factor_provision_periodo(), 5 / 30.0)
        self.assertAlmostEqual(q2._ne_factor_provision_periodo(), 0.5)
        self._assert_provisiones(mes, self._esperado_6m(mes, 20 / 30.0))
        self._assert_provisiones(q1, self._esperado_6m(q1, 5 / 30.0))

    def test_una_ausencia_no_descuenta_la_provision_decision_a(self):
        """Decision A del diseno: la provision NO lee ``_ne_dias_pagables()`` (que resta toda ausencia, tambien las remuneradas). Aunque ese
        metodo diga 0 dias pagables (una quincena completa de vacaciones), la provision de la quincena sigue siendo la mitad y el metodo ni se llama."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15))
        llamadas = []

        def sin_dias_pagables(slip, valores=None):
            llamadas.append(slip.id)
            return 0.0

        with patch.object(self.env.registry['hr.payslip'], '_ne_dias_pagables', sin_dias_pagables):
            self.assertAlmostEqual(recibo._ne_factor_provision_periodo(), 0.5)
            self._assert_provisiones(recibo, self._esperado_6m(recibo, 0.5))
        self.assertEqual(llamadas, [], 'La provision no debe depender de _ne_dias_pagables()')

    def test_salario_integral_usa_el_factor_integral_y_su_quincena_es_la_mitad(self):
        """Integral: base = sueldo x factor integral (sin auxilio) para prima y cesantias; vacaciones siguen con el sueldo (sueldo x 30 / 720)."""
        sueldo = 30000000.0
        mes = self._recibo(date(2026, 4, 1), date(2026, 4, 30), wage=sueldo, integral=True, name='Integral mes')
        quincena = self._recibo(date(2026, 4, 1), date(2026, 4, 15), wage=sueldo, integral=True, name='Integral q1')
        factor_integral = mes._rule_parameter('l10n_co_factor_integral_salary', mes.date_from)
        mensual = sueldo * factor_integral / 12.0
        real_mes = self._provisiones(mes)
        real_q = self._provisiones(quincena)
        self.assertAlmostEqual(real_mes['CO_PROV_PRIMA'], mensual, delta=0.005)
        self.assertAlmostEqual(real_mes['CO_PROV_CESANTIAS'], mensual, delta=0.005)
        self.assertAlmostEqual(real_mes['CO_PROV_VACACIONES'], sueldo / 24.0, delta=0.005)
        for codigo, _xmlid in _REGLAS:
            self.assertAlmostEqual(real_q[codigo], real_mes[codigo] / 2, delta=0.005, msg=codigo)

    def test_con_y_sin_auxilio_de_transporte(self):
        """Sueldo <= 2 SMMLV: la base lleva el auxilio y la quincena es la mitad de (sueldo + auxilio) / 12. Sueldo mayor: sin auxilio (250.000 por quincena)."""
        bajo = self._recibo(date(2026, 4, 1), date(2026, 4, 15), wage=1800000.0, name='Con auxilio')
        smmlv = bajo._rule_parameter('l10n_co_smmlv', bajo.date_from)
        auxilio = bajo._rule_parameter('l10n_co_aux_transporte', bajo.date_from)
        self.assertLessEqual(1800000.0, 2 * smmlv, 'Premisa: este sueldo recibe auxilio')
        real = self._provisiones(bajo)
        esperado = (1800000.0 + auxilio) / 12.0 * 0.5
        self.assertAlmostEqual(real['CO_PROV_PRIMA'], esperado, delta=0.005)
        self.assertAlmostEqual(real['CO_PROV_CESANTIAS'], esperado, delta=0.005)
        self.assertAlmostEqual(real['CO_PROV_VACACIONES'], 1800000.0 / 24.0 * 0.5, delta=0.005)   # vacaciones: sin auxilio
        alto = self._recibo(date(2026, 4, 1), date(2026, 4, 15), name='Sin auxilio')
        self._premisa_sin_auxilio(alto)
        self.assertAlmostEqual(self._provisiones(alto)['CO_PROV_PRIMA'], 250000.0, delta=0.005)

    def test_los_intereses_de_cesantias_siguen_a_las_cesantias_y_son_proporcionales(self):
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15))
        mensual = self._provisiones(self._recibo(date(2026, 4, 1), date(2026, 4, 30), name='Mes'))
        real = self._provisiones(recibo)
        pct = self._pct_intereses(recibo)
        self.assertAlmostEqual(real['CO_PROV_INT_CES'], real['CO_PROV_CESANTIAS'] * pct / 100, delta=0.005)
        self.assertAlmostEqual(real['CO_PROV_INT_CES'], mensual['CO_PROV_INT_CES'] / 2, delta=0.005)

    def test_semanal_usa_siete_dias_sobre_treinta(self):
        """Contrato semanal: una semana de 7 dias calendario cubre 7/30 del mes (``_ne_contar_dias``: valor del dia = salario / 30)."""
        recibo = self._recibo(date(2026, 4, 6), date(2026, 4, 12), semanal=True, name='Semanal')
        self.assertTrue(recibo._ne_es_semanal(), 'Premisa: el contrato es semanal')
        self.assertAlmostEqual(recibo._ne_factor_provision_periodo(), 7 / 30.0)
        self._assert_provisiones(recibo, self._esperado_6m(recibo, 7 / 30.0))

    def test_las_provisiones_viven_solo_en_la_estructura_general_y_usan_el_factor(self):
        """Guarda estructural: 4 reglas ``CO_PROV_*``, todas de la estructura general; prima, cesantias y vacaciones llaman al factor y los
        intereses lo heredan por la linea de cesantias (no lo repiten)."""
        reglas = self.env['hr.salary.rule'].search([('code', '=like', 'CO_PROV_%')])
        self.assertEqual(set(reglas.mapped('code')), {codigo for codigo, _x in _REGLAS})
        self.assertEqual(reglas.mapped('struct_id'), self.est_general)
        for codigo in ('CO_PROV_PRIMA', 'CO_PROV_CESANTIAS', 'CO_PROV_VACACIONES'):
            regla = reglas.filtered(lambda r, c=codigo: r.code == c)
            self.assertIn('payslip._ne_factor_provision_periodo()', regla.amount_python_compute, codigo)
        intereses = reglas.filtered(lambda r: r.code == 'CO_PROV_INT_CES')
        self.assertIn("result_rules['CO_PROV_CESANTIAS']['total']", intereses.amount_python_compute)
        self.assertNotIn('_ne_factor_provision_periodo', intereses.amount_python_compute)

    def test_liquidacion_prima_y_bonificacion_no_cambian(self):
        """Ninguna regla fuera de las 3 provisiones usa el factor, y las estructuras de liquidacion, prima y bonificacion no tienen provisiones."""
        con_factor = self.env['hr.salary.rule'].search([('amount_python_compute', 'ilike', '_ne_factor_provision_periodo')])
        self.assertEqual(set(con_factor.mapped('code')), {'CO_PROV_PRIMA', 'CO_PROV_CESANTIAS', 'CO_PROV_VACACIONES'})
        for estructura in (self.est_liquidacion, self.est_prima, self.est_bonificacion):
            self.assertFalse(estructura.rule_ids.filtered(lambda r: r.code.startswith('CO_PROV_')), estructura.name)
