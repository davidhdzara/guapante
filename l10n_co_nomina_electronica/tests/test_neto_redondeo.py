# -*- coding: utf-8 -*-
"""E-8 (H-QA-025): el neto sale de las líneas REDONDEADAS, y con eso el asiento de la liquidación cuadra.

Defecto: Odoo suma a ``categories`` el total EXACTO de cada regla y solo al guardar la línea lo redondea a 2 decimales; las
reglas de neto sumaban esos valores exactos y el neto guardado podía quedar un centavo lejos de la suma de las líneas (que es
lo que lee el asiento contable: débitos = devengados guardados; créditos = deducciones + neto guardados).

Casos reales de QA (valores exactos calculados aparte, con Decimal, sin importar el módulo):
- Acevedo (recibo 63679): prima y cesantías 166.666,666… (se guardan HACIA ARRIBA, .67), intereses 1.666,666…, vacaciones
  72.954,375: neto exacto 2.018.786,975 -> 2.018.786,98 guardado; suma de las líneas guardadas 2.018.786,99.
- Orozco (empleado 51690, retiro 20-04-2026): cesantías y prima 611.111,111… (HACIA ABAJO, .11), intereses 22.407,407…,
  vacaciones 559.316,875: neto exacto 2.877.834,9046 -> .90 guardado; suma de las líneas 2.877.834,91.
El defecto no depende del sentido del redondeo: las pruebas cubren los dos.

Las pruebas «de ayudante» arman ``result_rules`` a mano (totales sin redondear, como los deja el motor) y no dependen de work
entries ni de calendarios; las de integración corren ``compute_sheet()`` y comprueban contra las líneas GUARDADAS. NO ejecutadas
(no hay Odoo local) cuando se escribieron.
"""

from datetime import date

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import float_compare, float_round

NETOS = ('CO_NETO', 'CO_LIQ_NETO', 'CO_PRIMA_NETO', 'CO_BON_NETO')
AUX_TRANSPORTE_2026 = 249095.0
SMMLV_2026 = 1750905.0


def _totales(**reglas):
    """``result_rules`` como lo deja el motor: {código: {'total': total SIN redondear}}."""
    return {codigo: {'total': total} for codigo, total in reglas.items()}


@tagged('post_install', '-at_install')
class TestNetoRedondeo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Neto Redondeo'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Neto Redondeo', 'country_id': cls.env.ref('base.co').id})
        ref = cls.env.ref
        cls.est_general = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.est_liquidacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.est_prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.est_bonificacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion')
        cls.Categoria = cls.env['hr.salary.rule.category']

    # ── fixtures ─────────────────────────────────────────────────────
    def _recibo(self, estructura, name, wage, date_from, date_to, date_start=date(2024, 3, 1)):
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': name,
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato %s' % name, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.structure_type.id, 'wage': wage, 'date_start': date_start, 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': name, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': estructura.id, 'date_from': date_from, 'date_to': date_to})

    def _categorias(self, codigo):
        return self.Categoria.search([('id', 'child_of', self.Categoria.search([('code', '=', codigo)]).ids)])

    def _linea(self, recibo, codigo):
        linea = recibo.line_ids.filtered(lambda l: l.code == codigo)
        self.assertTrue(linea, 'La regla %s no generó línea.' % codigo)
        return linea

    def _asiento(self, recibo, categoria_devengado='DEV'):
        """Lo que hace el asiento nativo con las líneas GUARDADAS (hr_payroll_account._prepare_slip_lines): el monto positivo de
        un devengado se debita, el negativo de una deducción se acredita y el neto por pagar se acredita. Devuelve (débitos,
        créditos)."""
        devengados, deducciones = self._categorias(categoria_devengado), self._categorias('DEDU')
        lineas = recibo.line_ids.filtered(lambda l: l.code not in NETOS)
        neto = recibo.line_ids.filtered(lambda l: l.code in NETOS)
        self.assertEqual(len(neto), 1, 'El recibo debe tener exactamente una línea de neto del módulo.')
        debitos = sum(l.total for l in lineas if l.category_id in devengados)
        creditos = -sum(l.total for l in lineas if l.category_id in deducciones) + neto.total
        return debitos, creditos

    def _assert_cuadra(self, recibo, categoria_devengado='DEV'):
        debitos, creditos = self._asiento(recibo, categoria_devengado)
        self.assertEqual(
            float_compare(debitos, creditos, precision_digits=2), 0,
            'El asiento no cuadra en %s: débitos %.2f, créditos %.2f (diferencia %.2f)' % (
                recibo.name, debitos, creditos, debitos - creditos))

    # ── el redondeo de la moneda ─────────────────────────────────────
    def test_redondea_a_los_decimales_de_la_moneda_de_la_compania_y_simetrico(self):
        recibo = self._recibo(self.est_general, 'Moneda', 3000000.0, date(2026, 9, 1), date(2026, 9, 15))
        self.assertEqual(recibo.company_id.currency_id.decimal_places, 2)
        self.assertEqual(recibo._ne_redondear_moneda(0.125), 0.13)
        self.assertEqual(recibo._ne_redondear_moneda(-0.125), -0.13)
        self.assertEqual(recibo._ne_redondear_moneda(166666.6666667), 166666.67)
        self.assertEqual(recibo._ne_redondear_moneda(611111.1111111), 611111.11)

    # ── casos reales: liquidación (ayudante, valores exactos de QA) ──
    def _liquidacion_acevedo(self):
        base = SMMLV_2026 + AUX_TRANSPORTE_2026                                  # 2.000.000
        return _totales(
            CO_LIQ_SALARIOS=SMMLV_2026, CO_LIQ_PRIMA=base / 360 * 30, CO_LIQ_CESANTIAS=base / 360 * 30,
            CO_LIQ_INT_CES=(base / 360 * 30) * 30 * 12 / 100 / 360, CO_LIQ_VACACIONES=SMMLV_2026 / 720 * 30,
            CO_LIQ_SALUD=-(SMMLV_2026 * 4 / 100), CO_LIQ_PENSION=-(SMMLV_2026 * 4 / 100))

    def _liquidacion_orozco(self):
        base = SMMLV_2026 + AUX_TRANSPORTE_2026
        salarios = SMMLV_2026 / 30 * 20                                          # 20 días de abril = 1.167.270
        return _totales(
            CO_LIQ_SALARIOS=salarios, CO_LIQ_CESANTIAS=base / 360 * 110, CO_LIQ_PRIMA=base / 360 * 110,
            CO_LIQ_INT_CES=(base / 360 * 110) * 110 * 12 / 100 / 360, CO_LIQ_VACACIONES=SMMLV_2026 / 720 * 230,
            CO_LIQ_SALUD=-(salarios * 4 / 100), CO_LIQ_PENSION=-(salarios * 4 / 100))

    def test_acevedo_el_neto_es_la_suma_de_las_lineas_redondeadas(self):
        """Redondeo hacia ARRIBA: el neto exacto 2.018.786,975 se guardaba .98; las líneas suman .99 (neto esperado de QA)."""
        recibo = self._recibo(self.est_liquidacion, 'Acevedo', SMMLV_2026, date(2025, 6, 1), date(2026, 1, 30))
        reglas = self._liquidacion_acevedo()
        exacto = sum(r['total'] for r in reglas.values())
        neto = recibo._ne_neto_redondeado(reglas, 'DEV')
        self.assertAlmostEqual(neto, 2018786.99, places=2)
        # Lo que daba antes (el exacto redondeado): 2.018.786,98; está en el borde .975, por eso solo se exige que sea OTRO.
        self.assertNotAlmostEqual(float_round(exacto, precision_digits=2), neto, places=2)

    def test_orozco_el_neto_es_la_suma_de_las_lineas_redondeadas(self):
        """Redondeo hacia ABAJO: el neto exacto 2.877.834,9046 se guardaba .90; las líneas suman .91."""
        recibo = self._recibo(self.est_liquidacion, 'Orozco', SMMLV_2026, date(2025, 9, 1), date(2026, 4, 20))
        reglas = self._liquidacion_orozco()
        exacto = sum(r['total'] for r in reglas.values())
        neto = recibo._ne_neto_redondeado(reglas, 'DEV')
        self.assertAlmostEqual(neto, 2877834.91, places=2)
        self.assertAlmostEqual(float_round(exacto, precision_digits=2), 2877834.90, places=2)   # lo que daba antes

    def _liquidacion_buenanos(self):
        base = SMMLV_2026 + AUX_TRANSPORTE_2026
        salarios = SMMLV_2026 / 30 * 10                                          # 10 días de mayo = 583.635
        return _totales(
            CO_LIQ_SALARIOS=salarios, CO_LIQ_CESANTIAS=base / 360 * 130, CO_LIQ_PRIMA=base / 360 * 130,
            CO_LIQ_INT_CES=(base / 360 * 130) * 130 * 12 / 100 / 360, CO_LIQ_VACACIONES=SMMLV_2026 / 720 * 250,
            CO_LIQ_SALUD=-(salarios * 4 / 100), CO_LIQ_PENSION=-(salarios * 4 / 100))

    def test_buenanos_control_el_neto_que_ya_cuadraba_no_cambia(self):
        """Caso de CONTROL de QA (empleado 51691, retiro 10-05-2026, 130 días): el neto exacto 2.620.638,0657 y la suma de
        las líneas guardadas (2.667.328,87 - 46.690,80) dan los dos 2.620.638,07: la corrección no debe alterarlo, y debe
        seguir verde junto a Acevedo y Orozco (+0,01 cada uno)."""
        recibo = self._recibo(self.est_liquidacion, 'Buenanos', SMMLV_2026, date(2025, 9, 1), date(2026, 5, 10))
        reglas = self._liquidacion_buenanos()
        lineas = {c: recibo._ne_redondear_moneda(r['total']) for c, r in reglas.items()}
        self.assertEqual(lineas['CO_LIQ_CESANTIAS'], 722222.22)
        self.assertEqual(lineas['CO_LIQ_INT_CES'], 31296.30)
        self.assertEqual(lineas['CO_LIQ_VACACIONES'], 607953.13)
        self.assertEqual(lineas['CO_LIQ_SALARIOS'], 583635.0)
        self.assertAlmostEqual(lineas['CO_LIQ_SALUD'] + lineas['CO_LIQ_PENSION'], -46690.80, places=2)
        neto = recibo._ne_neto_redondeado(reglas, 'DEV')
        self.assertAlmostEqual(neto, 2620638.07, places=2)
        exacto = float_round(sum(r['total'] for r in reglas.values()), precision_digits=2)
        self.assertAlmostEqual(neto, exacto, places=2)                              # el neto de antes es el mismo

    def test_las_lineas_de_acevedo_y_orozco_no_cambian(self):
        """El cambio no toca el importe de ninguna línea: solo cómo se suma el neto."""
        recibo = self._recibo(self.est_liquidacion, 'Importes', SMMLV_2026, date(2025, 6, 1), date(2026, 1, 30))
        acevedo = {c: recibo._ne_redondear_moneda(r['total']) for c, r in self._liquidacion_acevedo().items()}
        self.assertEqual(acevedo['CO_LIQ_PRIMA'], 166666.67)
        self.assertEqual(acevedo['CO_LIQ_INT_CES'], 1666.67)
        self.assertEqual(acevedo['CO_LIQ_VACACIONES'], 72954.38)
        orozco = {c: recibo._ne_redondear_moneda(r['total']) for c, r in self._liquidacion_orozco().items()}
        self.assertEqual(orozco['CO_LIQ_CESANTIAS'], 611111.11)
        self.assertEqual(orozco['CO_LIQ_INT_CES'], 22407.41)
        self.assertEqual(orozco['CO_LIQ_VACACIONES'], 559316.88)
        self.assertEqual(orozco['CO_LIQ_SALARIOS'], 1167270.0)

    # ── los otros tres tipos de recibo (ayudante) ────────────────────
    def test_nomina_general_neto_de_las_lineas_redondeadas_hacia_arriba_y_hacia_abajo(self):
        """Valores calculados aparte (BASICO = salario/30 x días, auxilio 249.095/30 x días, salud y pensión 4 % del básico):
        el neto exacto redondeado daba otra cifra que la suma de las líneas guardadas en los tres casos."""
        recibo = self._recibo(self.est_general, 'General', 1234567.0, date(2026, 9, 1), date(2026, 9, 15))
        for salario, dias, esperado in (
                (1234567.0, 7, 323142.54), (1400001.0, 12, 614838.36), (1500100.0, 7, 380143.64)):
            with self.subTest(salario=salario, dias=dias):
                basico = salario / 30 * dias
                reglas = _totales(
                    CO_BASICO=basico, CO_AUX_TRANS=AUX_TRANSPORTE_2026 / 30 * dias,
                    CO_SALUD_EMP=-(basico * 4 / 100), CO_PENSION_EMP=-(basico * 4 / 100))
                exacto = float_round(sum(r['total'] for r in reglas.values()), precision_digits=2)
                self.assertNotAlmostEqual(exacto, esperado, places=2)                  # lo que daba antes
                self.assertAlmostEqual(recibo._ne_neto_redondeado(reglas, 'DEV'), esperado, places=2)

    def test_prima_las_reglas_de_salud_y_pension_estan_inactivas_y_la_retencion_activa(self):
        """Desde .164 la prima no lleva salud ni pensión del empleado (CST art. 307): CO_PRIMA_SALUD y CO_PRIMA_PENSION están
        inactivas (hr_payroll_structure_special_data.xml) y ``struct_id.rule_ids`` -el recorrido del motor
        (hr_payroll/models/hr_payslip.py:944)- no las trae. CO_PRIMA_RETE (categoría DEDU) sí está activa."""
        codigos = set(self.est_prima.rule_ids.mapped('code'))
        self.assertNotIn('CO_PRIMA_SALUD', codigos)
        self.assertNotIn('CO_PRIMA_PENSION', codigos)
        self.assertIn('CO_PRIMA_RETE', codigos)
        self.assertEqual(self.est_prima.rule_ids.filtered(lambda r: r.code == 'CO_PRIMA_RETE').category_id.code, 'DEDU')

    def test_prima_sin_deducciones_neto_es_el_valor_de_la_prima(self):
        """Prima de 11 días sobre 2.000.000: 2.000.000 / 360 x 11 = 61.111,111...: la línea guarda 61.111,11 y, sin salud ni
        pensión, ese es el neto. Las reglas inactivas que alguien meta en ``result_rules`` no suman: el motor no las evalúa."""
        recibo = self._recibo(self.est_prima, 'PrimaSinDed', 1750905.0, date(2026, 7, 1), date(2026, 12, 31))
        valor = 2000000.0 / 360 * 11
        self.assertAlmostEqual(recibo._ne_neto_redondeado(_totales(CO_PRIMA_VALOR=valor), 'PREST'), 61111.11, places=2)
        con_inactivas = _totales(
            CO_PRIMA_VALOR=valor, CO_PRIMA_SALUD=-(valor * 4 / 100), CO_PRIMA_PENSION=-(valor * 4 / 100))
        self.assertAlmostEqual(recibo._ne_neto_redondeado(con_inactivas, 'PREST'), 61111.11, places=2)

    def test_prima_neto_usa_prestaciones_mas_deducciones(self):
        """Prima 10,006 (línea 10,01) y retención -5,004 (línea -5,00): el neto exacto redondeado daría 5,00 y la suma de las
        líneas guardadas da 5,01. Con CO_PRIMA_RETE (activa en la estructura) en lugar de salud/pensión (inactivas)."""
        recibo = self._recibo(self.est_prima, 'PrimaRete', 1750905.0, date(2026, 7, 1), date(2026, 12, 31))
        reglas = _totales(CO_PRIMA_VALOR=10.006, CO_PRIMA_RETE=-5.004)
        self.assertEqual(recibo._ne_redondear_moneda(10.006), 10.01)
        self.assertEqual(recibo._ne_redondear_moneda(-5.004), -5.0)
        self.assertAlmostEqual(float_round(sum(r['total'] for r in reglas.values()), precision_digits=2), 5.00, places=2)
        self.assertAlmostEqual(recibo._ne_neto_redondeado(reglas, 'PREST'), 5.01, places=2)

    def test_bonificacion_neto_de_las_lineas_redondeadas(self):
        recibo = self._recibo(self.est_bonificacion, 'Bonificacion', 1750905.0, date(2026, 9, 1), date(2026, 9, 30))
        valor = 2000000.0 / 360 * 11
        reglas = _totales(
            CO_BON_VALOR=valor, CO_BON_SALUD=-(valor * 4 / 100), CO_BON_PENSION=-(valor * 4 / 100))
        self.assertAlmostEqual(recibo._ne_neto_redondeado(reglas, 'DEV'), 56222.23, places=2)

    # ── qué entra y qué no entra en el neto ──────────────────────────
    def test_no_suman_los_totales_de_display_ni_las_reglas_que_no_se_evaluaron(self):
        recibo = self._recibo(self.est_general, 'Alcance', 1000000.0, date(2026, 9, 1), date(2026, 9, 15))
        base = _totales(CO_BASICO=500000.0, CO_SALUD_EMP=-20000.0, CO_PENSION_EMP=-20000.0)
        self.assertAlmostEqual(recibo._ne_neto_redondeado(base, 'DEV'), 460000.0, places=2)
        # CO_BRUTO es un total de display (categoría TOT_DISPLAY, no hija de DEV): no se suma otra vez.
        con_total = dict(base, CO_BRUTO={'total': 500000.0})
        self.assertAlmostEqual(recibo._ne_neto_redondeado(con_total, 'DEV'), 460000.0, places=2)
        # El auxilio no estaba en result_rules (su condición no se cumplió): no suma, y no falla.
        self.assertNotIn('CO_AUX_TRANS', base)

    def test_las_subcategorias_suman_como_categories(self):
        """Hora extra (HEX, hija de DEV_SAL, hija de DEV) y no salarial (DEV_NOSAL) entran en DEV; seguridad social (SS_EMP,
        hija de DEDU) entra en DEDU: la misma agrupación de categories['DEV'] y categories['DEDU']."""
        recibo = self._recibo(self.est_general, 'Subcategorias', 1000000.0, date(2026, 9, 1), date(2026, 9, 15))
        reglas = _totales(CO_BASICO=100.004, CO_HED=50.004, CO_AUX_TRANS=10.004, CO_SALUD_EMP=-4.004, CO_PENSION_EMP=-4.004)
        # 100.00 + 50.00 + 10.00 - 4.00 - 4.00
        self.assertAlmostEqual(recibo._ne_neto_redondeado(reglas, 'DEV'), 152.0, places=2)

    # ── las 4 reglas de neto usan el ayudante ────────────────────────
    def test_las_reglas_de_neto_de_las_4_estructuras_usan_el_ayudante(self):
        for estructura, codigo, categoria in (
                (self.est_general, 'CO_NETO', 'DEV'), (self.est_liquidacion, 'CO_LIQ_NETO', 'DEV'),
                (self.est_prima, 'CO_PRIMA_NETO', 'PREST'), (self.est_bonificacion, 'CO_BON_NETO', 'DEV')):
            with self.subTest(regla=codigo):
                regla = estructura.rule_ids.filtered(lambda r: r.code == codigo)
                self.assertEqual(len(regla), 1)
                # Solo las líneas de código (los comentarios de la fórmula aún explican por qué categories['DEDU'] ya incluye SS_EMP).
                codigo_fuente = [l.strip() for l in regla.amount_python_compute.splitlines()
                                 if l.strip() and not l.strip().startswith('#')]
                self.assertEqual(codigo_fuente, ["result = payslip._ne_neto_redondeado(result_rules, '%s')" % categoria])

    # ── integración: compute_sheet() y el asiento ────────────────────
    def test_liquidacion_estilo_acevedo_el_neto_guardado_es_la_suma_de_las_lineas_y_el_asiento_cuadra(self):
        """Contrato de 1.750.905 (SMMLV 2026) con retiro el 30-ene-2026: prima y cesantías de 30 días sobre 2.000.000 =
        166.666,666… (los tercios de Acevedo). Se compara con las líneas GUARDADAS."""
        recibo = self._recibo(
            self.est_liquidacion, 'LiqAcevedoIntegracion', SMMLV_2026, date(2025, 6, 1), date(2026, 1, 30),
            date_start=date(2025, 6, 1))
        recibo.compute_sheet()
        self.assertAlmostEqual(self._linea(recibo, 'CO_LIQ_PRIMA').total, 166666.67, places=2)
        self.assertAlmostEqual(self._linea(recibo, 'CO_LIQ_CESANTIAS').total, 166666.67, places=2)
        neto = self._linea(recibo, 'CO_LIQ_NETO').total
        suma = sum(l.total for l in recibo.line_ids.filtered(
            lambda l: l.code not in NETOS and l.category_id in self._categorias('DEV') | self._categorias('DEDU')))
        self.assertAlmostEqual(neto, suma, places=2)
        self._assert_cuadra(recibo)

    def test_liquidacion_retiro_en_abril_el_asiento_cuadra(self):
        """Retiro el 20-abr-2026 (caso Orozco): redondeo hacia abajo."""
        recibo = self._recibo(
            self.est_liquidacion, 'LiqOrozcoIntegracion', SMMLV_2026, date(2025, 9, 1), date(2026, 4, 20),
            date_start=date(2025, 9, 1))
        recibo.compute_sheet()
        self._assert_cuadra(recibo)

    def test_nomina_general_quincena_con_fracciones_el_asiento_cuadra(self):
        for salario, ingreso in ((1234567.0, date(2026, 9, 9)), (1400001.0, date(2026, 9, 4)), (1500100.0, date(2026, 9, 9))):
            with self.subTest(salario=salario):
                recibo = self._recibo(
                    self.est_general, 'General%d' % salario, salario, date(2026, 9, 1), date(2026, 9, 15), date_start=ingreso)
                recibo.compute_sheet()
                self._assert_cuadra(recibo)

    def test_prima_con_fracciones_el_asiento_cuadra(self):
        recibo = self._recibo(
            self.est_prima, 'PrimaIntegracion', 1750905.0, date(2026, 7, 1), date(2026, 12, 31), date_start=date(2026, 8, 10))
        recibo.compute_sheet()
        self._assert_cuadra(recibo, 'PREST')
