# -*- coding: utf-8 -*-
"""Provisiones de prestaciones (CO_PROV_PRIMA / CO_PROV_CESANTIAS / CO_PROV_INT_CES / CO_PROV_VACACIONES) sobre la BASE PRESTACIONAL DEVENGADA (.303, doc 78).

Historia: .279 (QA, prenomina de abril de 2026 de Guapante, quincenal) hizo proporcional al periodo el valor MENSUAL que daban las 4 reglas sobre el sueldo y el
auxilio del CONTRATO (``_ne_factor_provision_periodo``). .303 (decisiones del TL del 22-nov) cambia la base: cada provisión es lo que ESTE recibo devengó
(las reglas ya calculadas con la marca «Base de prima y cesantías» o «Base de vacaciones») dividido por un parámetro con vigencia:
- prima y cesantías: salario (CST art. 127, con extras y recargos) + auxilio de transporte pagado (Ley 1/1963 art. 7) ÷ ``l10n_co_divisor_prov_prima`` / ``..._cesantias``
  (12 de fábrica); intereses = cesantías × ``l10n_co_pct_intereses_cesantias`` / 100;
- vacaciones: salario ordinario (CST art. 192: sin horas extras ni trabajo en días de descanso obligatorio; el recargo nocturno ordinario sí; sin auxilio de transporte) ×
  ``l10n_co_dias_mes_comercial`` / ``l10n_co_divisor_vacaciones`` (30 / 720 = 1/24);
- salario integral: prima, cesantías e intereses = 0 (CST art. 132 num. 2); las vacaciones sí, sobre lo devengado.
Ya no hay factor de periodo: lo devengado de una quincena, una semana, un ingreso a mitad de mes o un mes con ausencias sin pago ya trae su fracción.

Valores a mano con sueldo 6.000.000 (> 2 SMMLV: sin auxilio de transporte): por mes, prima y cesantías 6.000.000 / 12 = 500.000 y vacaciones 6.000.000 / 24 = 250.000; por
quincena, 250.000 y 125.000. Abril de 2026 tiene 30 días, mayo 31 y febrero 28 (último día real = día comercial 30). NO ejecutadas en Odoo; necesitan ``-u`` (marcas y
parámetros nuevos)."""

from datetime import date

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

_REGLAS = (
    ('CO_PROV_PRIMA', 'hr_salary_rule_co_prov_prima'),
    ('CO_PROV_CESANTIAS', 'hr_salary_rule_co_prov_cesantias'),
    ('CO_PROV_INT_CES', 'hr_salary_rule_co_prov_int_cesantias'),   # lee la línea de cesantías: va después de ella
    ('CO_PROV_VACACIONES', 'hr_salary_rule_co_prov_vacaciones'),
)
_SUELDO = 6000000.0
_MENSUAL_SUELDO = {'CO_PROV_PRIMA': 500000.0, 'CO_PROV_CESANTIAS': 500000.0, 'CO_PROV_VACACIONES': 250000.0}
_G_MANAGER = 'hr_payroll.group_hr_payroll_manager'
# La siembra de las dos marcas (decisiones del TL del 22-nov y doc 78 §3).
_BASE_PRIMA_CESANTIAS = {
    'CO_BASICO', 'CO_COMISIONES', 'CO_BONIF_SAL', 'CO_VIATICOS_SAL', 'CO_HED', 'CO_HEN', 'CO_HRN', 'CO_HEDDF', 'CO_HENDF', 'CO_HRDDF', 'CO_HRNDF', 'CO_AUX_TRANS', 'CO_VAC',
    'CO_LIC_REM', 'CO_APOYO_SOST_PRAC'}      # H-F1-09: el apoyo de la fase practica del aprendiz es base de las prestaciones (decision del TL del 22-nov)
_BASE_VACACIONES = {'CO_BASICO', 'CO_COMISIONES', 'CO_BONIF_SAL', 'CO_VIATICOS_SAL', 'CO_HRN', 'CO_VAC', 'CO_LIC_REM', 'CO_APOYO_SOST_PRAC'}


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

    def _calculadas(self, recibo):
        """Valor de las 4 provisiones que guarda el motor (``compute_sheet``) en las líneas del recibo."""
        recibo.compute_sheet()
        return {codigo: sum(recibo.line_ids.filtered(lambda l, c=codigo: l.code == c).mapped('total')) for codigo, _x in _REGLAS}

    def _linea(self, recibo, codigo):
        return sum(recibo.line_ids.filtered(lambda l: l.code == codigo).mapped('total'))

    def _directas(self, recibo, **devengado):
        """Valor de las 4 reglas con el motor de reglas (``_compute_rule``) sobre devengados SINTÉTICOS (``CODIGO=total``), en el orden del motor: los intereses leen
        ``result_rules['CO_PROV_CESANTIAS']['total']`` ya calculado."""
        resultados = {codigo: {'total': total} for codigo, total in devengado.items()}
        valores = {}
        for codigo, xmlid in _REGLAS:
            regla = self.env.ref('l10n_co_nomina_electronica.%s' % xmlid)
            monto = regla._compute_rule({'payslip': recibo, 'contract': recibo.contract_id, 'result_rules': resultados})[0]
            valores[codigo] = monto
            resultados[codigo] = {'total': monto}
        return valores

    def _pct_intereses(self, recibo):
        return recibo._rule_parameter('l10n_co_pct_intereses_cesantias', recibo.date_from)

    def _esperado_6m(self, recibo, fraccion):
        """Provisión esperada de un recibo con sueldo 6.000.000 que cubre ``fraccion`` del mes."""
        valores = {codigo: valor * fraccion for codigo, valor in _MENSUAL_SUELDO.items()}
        valores['CO_PROV_INT_CES'] = _MENSUAL_SUELDO['CO_PROV_CESANTIAS'] * self._pct_intereses(recibo) / 100 * fraccion
        return valores

    def _assert_provisiones(self, recibo, esperado):
        real = self._calculadas(recibo)
        for codigo, valor in esperado.items():
            self.assertAlmostEqual(real[codigo], valor, delta=0.01, msg='%s: %s' % (codigo, recibo.name))

    def _premisa_sin_auxilio(self, recibo):
        smmlv = recibo._rule_parameter('l10n_co_smmlv', recibo.date_from)
        self.assertGreater(recibo.contract_id.wage, 2 * smmlv, 'Premisa: con este sueldo no hay auxilio de transporte')

    def _valor_del_parametro(self, codigo, valor, desde=date(2026, 1, 2)):
        parametro = self.env['hr.rule.parameter'].search([('code', '=', codigo)], limit=1)
        self.assertTrue(parametro, codigo)
        self.env['hr.rule.parameter.value'].create({'rule_parameter_id': parametro.id, 'parameter_value': str(valor), 'date_from': desde})

    # ── con el motor completo (``compute_sheet``): los mismos valores de .279 donde lo devengado es sueldo (+ auxilio) ────────────────────
    def test_mes_completo_da_el_mismo_valor_mensual_de_antes(self):
        """Abril 1 al 30, sueldo 6.000.000: lo devengado es el sueldo completo; las 4 provisiones valen lo mismo que antes (prima y cesantías 500.000, vacaciones 250.000)."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30))
        self._premisa_sin_auxilio(recibo)
        self._assert_provisiones(recibo, self._esperado_6m(recibo, 1.0))

    def test_quincena_1_al_15_es_la_mitad_y_la_linea_del_recibo_la_guarda(self):
        """Quincena 1 al 15 de abril: lo devengado es la mitad (3.000.000) y las líneas guardadas valen la mitad: 250.000, 250.000 y 125.000."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15))
        self._premisa_sin_auxilio(recibo)
        recibo.compute_sheet()
        self.assertAlmostEqual(self._linea(recibo, 'CO_BASICO'), _SUELDO / 2, delta=0.01, msg='Premisa: el sueldo de la quincena')
        esperado = self._esperado_6m(recibo, 0.5)
        for codigo, valor in esperado.items():
            linea = recibo.line_ids.filtered(lambda l, c=codigo: l.code == c)
            self.assertEqual(len(linea), 1, 'Falta la línea %s del recibo' % codigo)
            self.assertAlmostEqual(linea.total, valor, delta=0.01, msg=codigo)
        self.assertAlmostEqual(esperado['CO_PROV_PRIMA'], 250000.0, delta=0.005)
        self.assertAlmostEqual(esperado['CO_PROV_VACACIONES'], 125000.0, delta=0.005)

    def test_quincena_16_al_30_es_la_mitad(self):
        recibo = self._recibo(date(2026, 4, 16), date(2026, 4, 30), name='Q2')
        self._assert_provisiones(recibo, self._esperado_6m(recibo, 0.5))

    def test_quincena_16_al_31_de_un_mes_de_31_dias_es_la_mitad(self):
        """El último día real de cualquier mes es el día comercial 30: 16 al 31 de mayo = 15 días comerciales, no 16."""
        recibo = self._recibo(date(2026, 5, 16), date(2026, 5, 31))
        self._assert_provisiones(recibo, self._esperado_6m(recibo, 0.5))

    def test_febrero_completo_es_un_mes_y_su_segunda_quincena_la_mitad(self):
        """Febrero de 2026 (28 días): 1 al 28 = 30 comerciales y 16 al 28 = 15."""
        mes = self._recibo(date(2026, 2, 1), date(2026, 2, 28), name='Febrero mes')
        quincena = self._recibo(date(2026, 2, 16), date(2026, 2, 28), name='Febrero quincena')
        self._assert_provisiones(mes, self._esperado_6m(mes, 1.0))
        self._assert_provisiones(quincena, self._esperado_6m(quincena, 0.5))

    def test_dos_quincenas_suman_exactamente_el_mes(self):
        """Invariante contable: lo provisionado en las dos quincenas de abril = lo de un recibo mensual de abril, en las 4 reglas."""
        primera = self._calculadas(self._recibo(date(2026, 4, 1), date(2026, 4, 15), name='Q1'))
        segunda = self._calculadas(self._recibo(date(2026, 4, 16), date(2026, 4, 30), name='Q2'))
        mensual = self._calculadas(self._recibo(date(2026, 4, 1), date(2026, 4, 30), name='Mes'))
        for codigo, _xmlid in _REGLAS:
            self.assertAlmostEqual(primera[codigo] + segunda[codigo], mensual[codigo], delta=0.01, msg=codigo)

    def test_ingreso_a_mitad_de_mes_provisiona_solo_lo_devengado(self):
        """Contrato desde el 11-abr-2026: el mes devenga 20 días (11 al 30), la quincena 1 al 15 solo 5 y la 16 al 30 los 15 (la base es lo devengado)."""
        mes = self._recibo(date(2026, 4, 1), date(2026, 4, 30), inicio=date(2026, 4, 11), name='Ingreso mes')
        q1 = self._recibo(date(2026, 4, 1), date(2026, 4, 15), inicio=date(2026, 4, 11), name='Ingreso q1')
        mes.compute_sheet()
        self.assertAlmostEqual(self._linea(mes, 'CO_BASICO'), _SUELDO * 20 / 30.0, delta=0.01, msg='Premisa: el sueldo del mes cubre 20 días')
        self._assert_provisiones(mes, self._esperado_6m(mes, 20 / 30.0))
        self._assert_provisiones(q1, self._esperado_6m(q1, 5 / 30.0))

    def test_con_y_sin_auxilio_de_transporte_la_base_es_lo_que_paga_la_linea(self):
        """Sueldo <= 2 SMMLV: la línea CO_AUX_TRANS se paga (por días) y suma a prima y cesantías, no a vacaciones. Sueldo mayor: sin auxilio."""
        bajo = self._recibo(date(2026, 4, 1), date(2026, 4, 15), wage=1800000.0, name='Con auxilio')
        smmlv = bajo._rule_parameter('l10n_co_smmlv', bajo.date_from)
        self.assertLessEqual(1800000.0, 2 * smmlv, 'Premisa: este sueldo recibe auxilio')
        real = self._calculadas(bajo)
        sueldo_q, auxilio_q = self._linea(bajo, 'CO_BASICO'), self._linea(bajo, 'CO_AUX_TRANS')
        self.assertGreater(auxilio_q, 0.0, 'Premisa: se paga auxilio')
        self.assertAlmostEqual(real['CO_PROV_PRIMA'], (sueldo_q + auxilio_q) / 12.0, delta=0.01)
        self.assertAlmostEqual(real['CO_PROV_CESANTIAS'], (sueldo_q + auxilio_q) / 12.0, delta=0.01)
        self.assertAlmostEqual(real['CO_PROV_VACACIONES'], sueldo_q / 24.0, delta=0.01, msg='vacaciones: sin auxilio')
        alto = self._recibo(date(2026, 4, 1), date(2026, 4, 15), name='Sin auxilio')
        self._premisa_sin_auxilio(alto)
        self.assertAlmostEqual(self._calculadas(alto)['CO_PROV_PRIMA'], 250000.0, delta=0.01)

    def test_semanal_provisiona_lo_devengado_de_la_semana(self):
        """Contrato semanal: una semana de 7 días calendario devenga 7/30 del sueldo; la base es esa línea (``_ne_contar_dias``: valor del día = salario / 30)."""
        recibo = self._recibo(date(2026, 4, 6), date(2026, 4, 12), semanal=True, name='Semanal')
        self.assertTrue(recibo._ne_es_semanal(), 'Premisa: el contrato es semanal')
        recibo.compute_sheet()
        self.assertAlmostEqual(self._linea(recibo, 'CO_BASICO'), _SUELDO * 7 / 30.0, delta=0.01, msg='Premisa: el sueldo de la semana')
        self._assert_provisiones(recibo, self._esperado_6m(recibo, 7 / 30.0))

    # ── con devengados sintéticos: qué entra a cada base (marcas sembradas) ─────────────────────────────────────────────────────────
    def test_la_base_de_prima_y_cesantias_suma_salario_extras_recargos_y_auxilio_y_la_de_vacaciones_el_salario_ordinario(self):
        """Un devengado de cada clase, de 1.000 en 1.000: prima y cesantías suman TODO lo marcado (con extras y recargos y el auxilio); vacaciones, solo el salario ordinario."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30))
        devengado = {codigo: 1000.0 * (n + 1) for n, codigo in enumerate(sorted(_BASE_PRIMA_CESANTIAS))}
        real = self._directas(recibo, **devengado)
        divisor_prima = recibo._rule_parameter('l10n_co_divisor_prov_prima', recibo.date_from)
        self.assertAlmostEqual(real['CO_PROV_PRIMA'], sum(devengado.values()) / divisor_prima, delta=0.005)
        self.assertAlmostEqual(real['CO_PROV_CESANTIAS'], sum(devengado.values()) / divisor_prima, delta=0.005)
        solo_vacaciones = sum(total for codigo, total in devengado.items() if codigo in _BASE_VACACIONES)
        self.assertAlmostEqual(real['CO_PROV_VACACIONES'], solo_vacaciones / 24.0, delta=0.005)

    def test_las_horas_extras_y_el_trabajo_en_dia_de_descanso_no_entran_a_vacaciones_art_192_pero_el_recargo_nocturno_ordinario_si(self):
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30))
        base = self._directas(recibo, CO_BASICO=1000000.0)
        for codigo in ('CO_HED', 'CO_HEN', 'CO_HEDDF', 'CO_HENDF', 'CO_HRDDF', 'CO_HRNDF'):
            real = self._directas(recibo, CO_BASICO=1000000.0, **{codigo: 120000.0})
            self.assertAlmostEqual(real['CO_PROV_PRIMA'] - base['CO_PROV_PRIMA'], 120000.0 / 12.0, delta=0.005, msg='%s entra a la prima' % codigo)
            self.assertAlmostEqual(real['CO_PROV_VACACIONES'], base['CO_PROV_VACACIONES'], delta=0.005, msg='%s NO entra a vacaciones (art. 192)' % codigo)
        nocturno = self._directas(recibo, CO_BASICO=1000000.0, CO_HRN=120000.0)
        self.assertAlmostEqual(nocturno['CO_PROV_PRIMA'] - base['CO_PROV_PRIMA'], 120000.0 / 12.0, delta=0.005)
        self.assertAlmostEqual(nocturno['CO_PROV_VACACIONES'] - base['CO_PROV_VACACIONES'], 120000.0 / 24.0, delta=0.005, msg='el recargo nocturno ordinario SÍ entra')

    def test_el_auxilio_de_transporte_entra_a_prima_y_cesantias_y_no_a_vacaciones(self):
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30))
        base = self._directas(recibo, CO_BASICO=1000000.0)
        con = self._directas(recibo, CO_BASICO=1000000.0, CO_AUX_TRANS=200000.0)
        self.assertAlmostEqual(con['CO_PROV_PRIMA'] - base['CO_PROV_PRIMA'], 200000.0 / 12.0, delta=0.005)
        self.assertAlmostEqual(con['CO_PROV_CESANTIAS'] - base['CO_PROV_CESANTIAS'], 200000.0 / 12.0, delta=0.005)
        self.assertAlmostEqual(con['CO_PROV_VACACIONES'], base['CO_PROV_VACACIONES'], delta=0.005, msg='Ley 1/1963: solo prestaciones sociales')

    def test_lo_que_no_es_base_no_mueve_ninguna_provision_decision_del_tl(self):
        """Pagos no salariales, vacaciones compensadas, incapacidades y licencias de ley, prestaciones e indemnización: FUERA de las dos bases (por prudencia; límite
        conocido a revisar con datos reales)."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30))
        base = self._directas(recibo, CO_BASICO=1000000.0)
        fuera = {codigo: 90000.0 for codigo in (
            'CO_BONIF_NOSAL', 'CO_AUX_ALIM', 'CO_VIATICOS_NOSAL', 'CO_DOTACION', 'CO_TELETRABAJO', 'CO_APOYO_SOST', 'CO_BONIF_RET', 'CO_INDEMNIZ', 'CO_VAC_COMP',
            'CO_INC_COMUN', 'CO_INC_LABORAL', 'CO_LIC_MAT', 'CO_LIC_PAT', 'CO_LIC_NR', 'CO_PRIMA', 'CO_CESANTIAS', 'CO_INT_CES')}
        real = self._directas(recibo, CO_BASICO=1000000.0, **fuera)
        for codigo, _xmlid in _REGLAS:
            self.assertAlmostEqual(real[codigo], base[codigo], delta=0.005, msg=codigo)

    def test_una_bonificacion_salarial_y_una_comision_mueven_las_cuatro_provisiones(self):
        """La regla de David del 22-nov (test_14 de «Cálculo del salario»): lo salarial que se agrega o se ajusta mueve las provisiones."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30))
        base = self._directas(recibo, CO_BASICO=_SUELDO)
        con = self._directas(recibo, CO_BASICO=_SUELDO, CO_BONIF_SAL=500000.0, CO_COMISIONES=300000.0)
        self.assertAlmostEqual(con['CO_PROV_PRIMA'] - base['CO_PROV_PRIMA'], 800000.0 / 12.0, delta=0.005)
        self.assertAlmostEqual(con['CO_PROV_CESANTIAS'] - base['CO_PROV_CESANTIAS'], 800000.0 / 12.0, delta=0.005)
        self.assertAlmostEqual(con['CO_PROV_VACACIONES'] - base['CO_PROV_VACACIONES'], 800000.0 / 24.0, delta=0.005)
        pct = self._pct_intereses(recibo)
        self.assertAlmostEqual(con['CO_PROV_INT_CES'], con['CO_PROV_CESANTIAS'] * pct / 100.0, delta=0.005)
        self.assertGreater(con['CO_PROV_INT_CES'], base['CO_PROV_INT_CES'])

    def test_vacaciones_disfrutadas_y_licencia_remunerada_siguen_causando(self):
        """El salario que se paga en las vacaciones o en una licencia remunerada es salario ordinario: sigue entrando a las dos bases (si no, la provisión caería en el mes de
        vacaciones aunque el empleado sigue causando)."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30))
        parcial = self._directas(recibo, CO_BASICO=4000000.0, CO_VAC=2000000.0)
        completo = self._directas(recibo, CO_BASICO=6000000.0)
        for codigo, _xmlid in _REGLAS:
            self.assertAlmostEqual(parcial[codigo], completo[codigo], delta=0.005, msg=codigo)
        licencia = self._directas(recibo, CO_BASICO=5000000.0, CO_LIC_REM=1000000.0)
        for codigo, _xmlid in _REGLAS:
            self.assertAlmostEqual(licencia[codigo], completo[codigo], delta=0.005, msg=codigo)

    def test_salario_integral_no_provisiona_prima_cesantias_ni_intereses_y_si_vacaciones(self):
        """CST art. 132 num. 2: el integral compensa «primas legales, extralegales, las cesantías y sus intereses … excepto las vacaciones». Las vacaciones, sobre lo devengado."""
        sueldo = 30000000.0
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30), wage=sueldo, integral=True, name='Integral mes')
        real = self._directas(recibo, CO_BASICO=sueldo)
        self.assertEqual((real['CO_PROV_PRIMA'], real['CO_PROV_CESANTIAS'], real['CO_PROV_INT_CES']), (0.0, 0.0, 0.0))
        self.assertAlmostEqual(real['CO_PROV_VACACIONES'], sueldo / 24.0, delta=0.005)
        engine = self._calculadas(self._recibo(date(2026, 4, 1), date(2026, 4, 15), wage=sueldo, integral=True, name='Integral q1'))
        self.assertEqual((engine['CO_PROV_PRIMA'], engine['CO_PROV_CESANTIAS'], engine['CO_PROV_INT_CES']), (0.0, 0.0, 0.0), 'También con el motor completo')
        self.assertAlmostEqual(engine['CO_PROV_VACACIONES'], sueldo / 24.0 / 2, delta=0.01)

    def test_los_intereses_de_cesantias_siguen_a_las_cesantias_y_son_proporcionales(self):
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15))
        mensual = self._calculadas(self._recibo(date(2026, 4, 1), date(2026, 4, 30), name='Mes'))
        real = self._calculadas(recibo)
        pct = self._pct_intereses(recibo)
        self.assertAlmostEqual(real['CO_PROV_INT_CES'], real['CO_PROV_CESANTIAS'] * pct / 100, delta=0.01)
        self.assertAlmostEqual(real['CO_PROV_INT_CES'], mensual['CO_PROV_INT_CES'] / 2, delta=0.01)

    # ── los parámetros (doc 10: lo que una ley puede cambiar no va en el código) ─────────────────────────────────────────────────────
    def test_los_divisores_salen_de_parametros_con_vigencia_y_cada_provision_usa_el_suyo(self):
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 30))
        for codigo in ('l10n_co_divisor_prov_prima', 'l10n_co_divisor_prov_cesantias'):
            self.assertEqual(recibo._rule_parameter(codigo, recibo.date_from), 12, codigo)
        base = self._directas(recibo, CO_BASICO=_SUELDO)
        self._valor_del_parametro('l10n_co_divisor_prov_prima', 6)
        cambio = self._directas(recibo, CO_BASICO=_SUELDO)
        self.assertAlmostEqual(cambio['CO_PROV_PRIMA'], base['CO_PROV_PRIMA'] * 2, delta=0.005, msg='la prima usa su divisor')
        self.assertAlmostEqual(cambio['CO_PROV_CESANTIAS'], base['CO_PROV_CESANTIAS'], delta=0.005, msg='las cesantías no se mueven con el de la prima')
        self._valor_del_parametro('l10n_co_divisor_prov_cesantias', 24)
        cambio = self._directas(recibo, CO_BASICO=_SUELDO)
        self.assertAlmostEqual(cambio['CO_PROV_CESANTIAS'], base['CO_PROV_CESANTIAS'] / 2, delta=0.005)
        self.assertAlmostEqual(cambio['CO_PROV_INT_CES'], base['CO_PROV_INT_CES'] / 2, delta=0.005, msg='los intereses siguen a las cesantías')
        self.assertAlmostEqual(cambio['CO_PROV_VACACIONES'], base['CO_PROV_VACACIONES'], delta=0.005)

    # ── guardas estructurales ─────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_las_provisiones_viven_solo_en_la_estructura_general_y_calculan_sobre_la_base_marcada(self):
        """4 reglas ``CO_PROV_*``, todas de la estructura general; prima, cesantías y vacaciones llaman a la base prestacional con su marca, y NINGUNA lleva el 12 ni un
        factor de periodo escritos en la fórmula (el 12 es un parámetro); los intereses leen la línea de cesantías."""
        reglas = self.env['hr.salary.rule'].search([('code', '=like', 'CO_PROV_%')])
        self.assertEqual(set(reglas.mapped('code')), {codigo for codigo, _x in _REGLAS})
        self.assertEqual(reglas.mapped('struct_id'), self.est_general)
        marca = {'CO_PROV_PRIMA': 'l10n_co_ne_base_prima_cesantias', 'CO_PROV_CESANTIAS': 'l10n_co_ne_base_prima_cesantias', 'CO_PROV_VACACIONES': 'l10n_co_ne_base_vacaciones'}
        for codigo, campo in marca.items():
            regla = reglas.filtered(lambda r, c=codigo: r.code == c)
            texto = '\n'.join(l for l in regla.amount_python_compute.splitlines() if not l.strip().startswith('#'))      # solo el código que se ejecuta
            self.assertIn("payslip._ne_base_prestacional(result_rules, '%s')" % campo, texto, codigo)
            self.assertNotIn('contract.wage', texto.replace('contract.l10n_co_ne_integral_salary', ''), '%s ya no usa el sueldo del contrato' % codigo)
            self.assertNotRegex(texto, r'/\s*12(\.0)?\b', '%s lleva el 12 escrito en la fórmula' % codigo)
            self.assertNotRegex(texto, r'/\s*24(\.0)?\b', '%s lleva el 24 escrito en la fórmula' % codigo)
        intereses = reglas.filtered(lambda r: r.code == 'CO_PROV_INT_CES')
        self.assertIn("result_rules['CO_PROV_CESANTIAS']['total']", intereses.amount_python_compute)
        for regla in reglas:
            self.assertFalse(regla.appears_on_payslip, regla.code)

    def test_ya_no_hay_factor_de_periodo(self):
        """.303 reemplaza al factor de .279: la base ya es lo devengado del periodo."""
        self.assertFalse(hasattr(self.env['hr.payslip'], '_ne_factor_provision_periodo'))
        self.assertFalse(self.env['hr.salary.rule'].search([('amount_python_compute', 'ilike', '_ne_factor_provision_periodo')]))

    def test_liquidacion_prima_y_bonificacion_no_tienen_provisiones(self):
        for estructura in (self.est_liquidacion, self.est_prima, self.est_bonificacion):
            self.assertFalse(estructura.rule_ids.filtered(lambda r: r.code.startswith('CO_PROV_')), estructura.name)

    def test_la_siembra_marca_solo_las_reglas_de_cada_base(self):
        """Doc 78 §3 con las decisiones del TL del 22-nov (las reglas son por estructura: se comparan los códigos)."""
        datos = self.env['ir.model.data'].search([('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', 'hr.salary.rule')])
        reglas = self.env['hr.salary.rule'].with_context(active_test=False).browse(datos.mapped('res_id')).exists()
        self.assertTrue(reglas)
        self.assertEqual(set(reglas.filtered('l10n_co_ne_base_prima_cesantias').mapped('code')), _BASE_PRIMA_CESANTIAS)
        self.assertEqual(set(reglas.filtered('l10n_co_ne_base_vacaciones').mapped('code')), _BASE_VACACIONES)
        self.assertFalse(reglas.filtered(lambda r: r.code.startswith('CO_PROV_') and (r.l10n_co_ne_base_prima_cesantias or r.l10n_co_ne_base_vacaciones)),
                         'Las provisiones no son base de sí mismas')

    def _usuario(self, login, grupos):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'email': '%s@example.com' % login, 'company_id': self.company.id,
            'company_ids': [(6, 0, self.company.ids)], 'groups_id': [(6, 0, [self.env.ref(g).id for g in grupos])]})

    def test_solo_el_administrador_del_sistema_cambia_las_marcas_modelo_y_vista(self):
        regla = self.env['hr.salary.rule'].search([('code', '=', 'CO_BASICO')], limit=1)
        gerente = self._usuario('gerente_base_prestacional', (_G_MANAGER, 'base.group_user'))
        administrador = self._usuario('administrador_base_prestacional', (_G_MANAGER, 'base.group_system', 'base.group_user'))
        for campo in ('l10n_co_ne_base_prima_cesantias', 'l10n_co_ne_base_vacaciones'):
            with self.assertRaisesRegex(AccessError, 'administrador del sistema'):
                regla.with_user(gerente).write({campo: False})
            self.assertTrue(regla[campo])
        with self.assertRaisesRegex(AccessError, 'administrador del sistema'):
            self.env['hr.salary.rule'].with_user(gerente).create({
                'name': 'Regla de prueba', 'code': 'CO_PRUEBA_BASE', 'sequence': 999, 'struct_id': regla.struct_id.id, 'category_id': regla.category_id.id,
                'l10n_co_ne_base_vacaciones': True})
        regla.with_user(administrador).write({'l10n_co_ne_base_vacaciones': False})
        self.assertFalse(regla.l10n_co_ne_base_vacaciones, 'El administrador sí')

        def campos_en_la_vista(usuario):
            arch = self.env['hr.salary.rule'].with_user(usuario).get_view(view_type='form')['arch']
            arbol = etree.fromstring(arch.encode('utf-8') if isinstance(arch, str) else arch)
            return [arbol.xpath("//field[@name='%s']" % c) for c in ('l10n_co_ne_base_prima_cesantias', 'l10n_co_ne_base_vacaciones')]
        self.assertFalse(any(campos_en_la_vista(gerente)), 'El gerente de nómina no ve las bases en el formulario de la regla')
        self.assertTrue(all(campos_en_la_vista(administrador)), 'El administrador del sistema sí')
