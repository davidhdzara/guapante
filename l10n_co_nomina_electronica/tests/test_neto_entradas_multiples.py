# -*- coding: utf-8 -*-
"""H-TL-009 (.277): el centavo con 2+ entradas del mismo tipo cuyo código coincide con el de una regla.

Mecanismo (hr_payroll/models/hr_payslip.py del servidor v18, líneas 957-990):
- ``rule.code in localdict['same_type_input_lines']`` (2+ entradas del mismo tipo; ``:817-821``): por CADA entrada se calcula
  ``tot_rule = payslip._get_payslip_line_total(amount, qty, rate, rule)`` (:961) y se ACUMULA
  ``result_rules_dict[rule.code]['total'] += tot_rule`` (:963-966), sin redondear;
- y se agrega UNA línea por entrada con su propio ``total`` (:972-986), que Odoo guarda redondeado a los decimales de la moneda.
El ayudante del neto de E-8 (``_ne_suma_lineas_redondeadas``) lee ese acumulado y lo redondea UNA vez: con 2 entradas de 10,004 el
acumulado es 20,008 -> 20,01, pero las líneas guardadas son 10,00 + 10,00 = 20,00. El neto guardado queda un centavo por encima de
la suma de las líneas y el asiento (débitos = devengados guardados; créditos = deducciones + neto) no cuadra. Aplica a las 39 reglas
cuyo código coincide con un tipo de entrada (CO_HED, CO_COMISIONES, CO_LIBRANZAS...). Con horas extra el caso es normal, no
excepcional: la fórmula es ``valor_hora * factor`` por ``result_qty = horas`` (``data/hr_payroll_structure_data.xml:209-213``), así
que cada línea trae decimales largos.

Corrección (.277): ``HrPayslipNeto._get_payslip_line_total`` redondea el total de cada entrada cuando el código tiene 2+ entradas y la
compañía es colombiana; el acumulado pasa a ser Σ round(entrada) = la suma de las líneas guardadas. Estas pruebas fijan: la
premisa del motor (una línea por entrada), el caso a mano de horas extra, el alcance del gancho (solo 2+ entradas y solo
Colombia; el resto IDÉNTICO al nativo) y el control con una entrada.
NO ejecutada en Odoo.
"""

from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import float_compare

NETOS = ('CO_NETO', 'CO_LIQ_NETO', 'CO_PRIMA_NETO', 'CO_BON_NETO')


@tagged('post_install', '-at_install')
class TestNetoEntradasMultiples(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Entradas Múltiples'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Entradas Múltiples', 'country_id': cls.env.ref('base.co').id})
        cls.est_general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.Categoria = cls.env['hr.salary.rule.category']

    def _recibo(self, name, salario=3000000.0):
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': name,
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato %s' % name, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.structure_type.id, 'wage': salario, 'date_start': date(2024, 3, 1),
            'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': name, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': self.est_general.id, 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15)})

    def _entradas(self, recibo, xmlid_tipo, codigo, *montos):
        for monto in montos:
            self.env['hr.payslip.input'].create({
                'payslip_id': recibo.id, 'input_type_id': self.env.ref('l10n_co_nomina_electronica.%s' % xmlid_tipo).id,
                'code': codigo, 'amount': monto})

    def _comisiones(self, recibo, *montos):
        self._entradas(recibo, 'input_co_comisiones', 'CO_COMISIONES', *montos)

    def _regla(self, codigo):
        regla = self.est_general.rule_ids.filtered(lambda r: r.code == codigo)
        self.assertEqual(len(regla), 1, 'Se esperaba UNA regla %s en la estructura general.' % codigo)
        return regla

    def _categorias(self, codigo):
        return self.Categoria.search([('id', 'child_of', self.Categoria.search([('code', '=', codigo)]).ids)])

    def _asiento(self, recibo):
        """Lo que hace el asiento nativo con las líneas GUARDADAS: devengados se debitan; deducciones y neto se acreditan."""
        devengados, deducciones = self._categorias('DEV'), self._categorias('DEDU')
        lineas = recibo.line_ids.filtered(lambda l: l.code not in NETOS)
        neto = recibo.line_ids.filtered(lambda l: l.code in NETOS)
        self.assertEqual(len(neto), 1)
        debitos = sum(l.total for l in lineas if l.category_id in devengados)
        creditos = -sum(l.total for l in lineas if l.category_id in deducciones) + neto.total
        return debitos, creditos

    def test_premisa_una_linea_por_entrada_y_cada_una_redondeada(self):
        recibo = self._recibo('Multiples Premisa')
        self._comisiones(recibo, 10.004, 10.004)
        recibo.compute_sheet()
        lineas = recibo.line_ids.filtered(lambda l: l.code == 'CO_COMISIONES')
        self.assertEqual(len(lineas), 2, 'Se esperaba UNA línea por entrada (hr_payslip.py:972-986).')
        self.assertEqual(sorted(lineas.mapped('total')), [10.0, 10.0])
        self.assertEqual(sum(lineas.mapped('total')), 20.0)           # 10,00 + 10,00; el acumulado del motor es 20,008

    def test_el_neto_guardado_es_la_suma_de_las_lineas_y_el_asiento_cuadra(self):
        """Sin la corrección el neto salía 0,01 por encima de la suma de las líneas (20,01 frente a 20,00)."""
        recibo = self._recibo('Multiples Neto')
        self._comisiones(recibo, 10.004, 10.004)
        recibo.compute_sheet()
        debitos, creditos = self._asiento(recibo)
        self.assertEqual(
            float_compare(debitos, creditos, precision_digits=2), 0,
            'El asiento no cuadra: débitos %.2f, créditos %.2f (diferencia %.2f)' % (debitos, creditos, debitos - creditos))

    def test_con_una_sola_entrada_no_cambia(self):
        """Control: con UNA entrada fraccionaria la línea y el acumulado coinciden y el asiento cuadra hoy."""
        recibo = self._recibo('Multiples Control')
        self._comisiones(recibo, 10.004)
        recibo.compute_sheet()
        debitos, creditos = self._asiento(recibo)
        self.assertEqual(float_compare(debitos, creditos, precision_digits=2), 0)

    def test_horas_extra_dos_entradas_de_3_horas_calculado_a_mano(self):
        """Salario 1.500.000, 2 entradas CO_HED de 3 h (septiembre 2026: 210 h/mes y factor 1,25).

        valor_hora = 1.500.000 / 210 = 7.142,857142857…; x 1,25 = 8.928,571428571…; x 3 h = 26.785,714285714…
        Cada línea se guarda en 26.785,71; las dos suman 53.571,42. El acumulado exacto (53.571,428571…) se redondeaba a
        53.571,43 (0,01 de más). Con el gancho el acumulado es 26.785,71 + 26.785,71 = 53.571,42."""
        recibo = self._recibo('Multiples HED', salario=1500000.0)
        self.assertEqual(recibo._rule_parameter('l10n_co_horas_mensuales', recibo.date_from), 210)
        self.assertEqual(recibo._rule_parameter('l10n_co_factor_hed', recibo.date_from), 1.25)
        self._entradas(recibo, 'input_co_hed', 'CO_HED', 3.0, 3.0)
        recibo.compute_sheet()
        lineas = recibo.line_ids.filtered(lambda l: l.code == 'CO_HED')
        self.assertEqual(len(lineas), 2, 'Se esperaba UNA línea por entrada (hr_payslip.py:972-986).')
        self.assertEqual(lineas.mapped('total'), [26785.71, 26785.71])
        self.assertEqual(float_compare(sum(lineas.mapped('total')), 53571.42, precision_digits=2), 0)
        # El neto es la suma de las líneas guardadas (devengados + deducciones) y el asiento cuadra.
        devengados, deducciones = self._categorias('DEV'), self._categorias('DEDU')
        lineas_netas = recibo.line_ids.filtered(lambda l: l.code not in NETOS)
        neto = recibo.line_ids.filtered(lambda l: l.code in NETOS)
        suma = (sum(l.total for l in lineas_netas if l.category_id in devengados)
                + sum(l.total for l in lineas_netas if l.category_id in deducciones))
        self.assertEqual(float_compare(neto.total, suma, precision_digits=2), 0,
                         'Neto %.2f frente a la suma de las líneas %.2f' % (neto.total, suma))
        debitos, creditos = self._asiento(recibo)
        self.assertEqual(float_compare(debitos, creditos, precision_digits=2), 0)

    def test_el_gancho_redondea_solo_codigos_con_dos_o_mas_entradas(self):
        """El gancho redondea el total de CADA entrada solo si el código tiene 2+ entradas; con 1 o 0 entradas devuelve el
        valor NATIVO (``amount * quantity * rate / 100.0``) sin tocarlo."""
        recibo = self._recibo('Multiples Gancho')
        self._comisiones(recibo, 10.004, 10.004)                           # 2 entradas
        self._entradas(recibo, 'input_co_hed', 'CO_HED', 3.0)             # 1 entrada
        valor_hora_factor = 1500000.0 / 210 * 1.25                         # 8.928,571428571…
        nativo = valor_hora_factor * 3 * 100 / 100.0                       # 26.785,714285714…
        con_dos = recibo._get_payslip_line_total(valor_hora_factor, 3, 100, self._regla('CO_COMISIONES'))
        self.assertAlmostEqual(con_dos, 26785.71, places=9)
        self.assertEqual(con_dos, round(con_dos, 2))                       # está redondeado a 2 decimales
        con_una = recibo._get_payslip_line_total(valor_hora_factor, 3, 100, self._regla('CO_HED'))
        self.assertEqual(con_una, nativo)                                  # IDÉNTICO al nativo
        sin_entradas = recibo._get_payslip_line_total(valor_hora_factor, 3, 100, self._regla('CO_BONIF_SAL'))
        self.assertEqual(sin_entradas, nativo)

    def test_el_resto_de_las_reglas_queda_identico_al_nativo(self):
        """En un recibo con 2 entradas de CO_COMISIONES, TODA otra regla de la estructura devuelve exactamente el valor nativo;
        sin entradas múltiples, ninguna regla (tampoco CO_COMISIONES) cambia."""
        valor = 8928.571428571429
        nativo = valor * 3 * 100 / 100.0
        con_multiples = self._recibo('Multiples Resto A')
        self._comisiones(con_multiples, 10.004, 10.004)
        sin_multiples = self._recibo('Multiples Resto B')
        self._comisiones(sin_multiples, 10.004)
        self.assertGreater(len(self.est_general.rule_ids), 1)
        for regla in self.est_general.rule_ids:
            esperado = round(nativo, 2) if regla.code == 'CO_COMISIONES' else nativo
            self.assertEqual(con_multiples._get_payslip_line_total(valor, 3, 100, regla), esperado, regla.code)
            self.assertEqual(sin_multiples._get_payslip_line_total(valor, 3, 100, regla), nativo, regla.code)

    def test_compania_no_colombiana_no_se_redondea(self):
        """Compañía no colombiana (se simula ``_ne_es_colombia``; no se crea una compañía de otro país porque autoinstala su
        localización): con 2 entradas el gancho devuelve el valor nativo sin redondear."""
        recibo = self._recibo('Multiples No CO')
        self._comisiones(recibo, 10.004, 10.004)
        valor = 8928.571428571429
        regla = self._regla('CO_COMISIONES')
        self.assertEqual(recibo._get_payslip_line_total(valor, 3, 100, regla), round(valor * 3, 2))     # Colombia: redondea
        with patch.object(self.env.registry['res.company'], '_ne_es_colombia', lambda compania: False):
            self.assertEqual(recibo._get_payslip_line_total(valor, 3, 100, regla), valor * 3 * 100 / 100.0)
