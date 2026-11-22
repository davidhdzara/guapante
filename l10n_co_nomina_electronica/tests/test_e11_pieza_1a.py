# -*- coding: utf-8 -*-
"""E11 pieza 1A (.285, doc 71a): sin literales donde ya hay configuración. CERO cambios en dinero: cada prueba compara contra lo que
hacía el código anterior (.284). NO EJECUTADAS en Odoo (sin acceso al servidor al escribirlas).

1. Tope del auxilio de transporte: el factor «2 × SMMLV» de 6 reglas XML sale del parámetro ``l10n_co_aux_transporte_tope_smmlv`` (2 desde
   2024-01-01). Con valor 2 las decisiones son las mismas que con el literal; cambiar el parámetro cambia el resultado.
2. Desglose del recibo (``_ne_desglose``): salud, pensión, FSP y retención salen de ``l10n_co_ne_dian_concept`` de la regla, no de listas de
   códigos. Las listas anteriores se copian aquí SOLO como referencia de equivalencia.
3. Tercero de las deducciones del contrato (``_ne_validar_terceros_deducciones``): sale de ``l10n_co_tercero_origen`` de la regla
   (``contract_*``), no de una tabla por código.
4. Se borró la copia «defensiva» del mapa de ausencias en ``_get_overlapping_leaves_data`` (nunca se ejecutaba: el mixin siempre está).
"""

import inspect
import re
from datetime import date

from odoo.addons.l10n_co_nomina_electronica.models.hr_payslip import HrPayslip
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

# Listas del código ANTERIOR (.284, hr_payslip.py:1284-1287 y :285-292): solo referencia de equivalencia, el módulo ya no las usa.
_DESGLOSE_ANTES = {
    'salud': ('CO_SALUD_EMP', 'CO_PRIMA_SALUD', 'CO_LIQ_SALUD', 'CO_BON_SALUD'),
    'pension': ('CO_PENSION_EMP', 'CO_PRIMA_PENSION', 'CO_LIQ_PENSION', 'CO_BON_PENSION'),
    'fsp': ('CO_FSP',),
    'retencion': ('CO_RETEFUENTE', 'CO_PRIMA_RETE', 'CO_LIQ_RETE', 'CO_BON_RETE'),
}
_CONCEPTO_DE_COLUMNA = {'salud': 'Salud', 'pension': 'FondoPension', 'fsp': 'FondoSP', 'retencion': 'RetencionFuente'}
_TERCERO_ANTES = {
    'CO_SINDICATO': 'l10n_co_ne_sindicato_partner_id',
    'CO_AFC': 'l10n_co_ne_afc_partner_id',
    'CO_PENSION_VOL': 'l10n_co_ne_pension_voluntaria_partner_id',
    'CO_PLAN_COMP': 'l10n_co_ne_plan_complementario_partner_id',
    'CO_COOPERATIVA': 'l10n_co_ne_cooperativa_partner_id',
    'CO_EDUCACION': 'l10n_co_ne_educacion_partner_id',
}
# Las reglas con el factor «2 × SMMLV» antes de .285 (doc 71a §5): código de regla de cada una. .303 (doc 78): CO_PROV_PRIMA y CO_PROV_CESANTIAS YA NO leen el tope: su base es lo
# que paga la línea del auxilio (CO_AUX_TRANS, que sí lo lee), no el sueldo y el auxilio del contrato.
_REGLAS_CON_TOPE = ('CO_AUX_TRANS', 'CO_PRIMA_BASE', 'CO_LIQ_PRIMA', 'CO_LIQ_CESANTIAS')
_PARAMETRO_TOPE = 'l10n_co_aux_transporte_tope_smmlv'
# Un literal 2 pegado a SMMLV: «... 'l10n_co_smmlv', fecha) * 2» o «(smmlv * 2)».
_LITERAL_DOS = re.compile(r"l10n_co_smmlv'[^\n]*\)\s*\*\s*2\b|\bsmmlv\s*\*\s*2\b")


@tagged('post_install', '-at_install')
class TestE11Pieza1A(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'l10n_co_ne_fuente_fecha_pago': 'recibo', 'name': 'Compañía de Prueba E11 1A'})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura E11 1A', 'country_id': cls.env.ref('base.co').id})
        cls.est_general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    # ── ayudas ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _recibo(self, date_from=date(2026, 4, 1), date_to=date(2026, 4, 30), wage=6000000.0, name='Recibo', estructura=None):
        employee = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': name,
            'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'name': 'Contrato %s' % name, 'employee_id': employee.id, 'company_id': self.company.id,
            'structure_type_id': self.tipo.id, 'wage': wage, 'date_start': date(2024, 1, 1), 'state': 'open'})
        return self.env['hr.payslip'].create({
            'name': name, 'employee_id': employee.id, 'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': (estructura or self.est_general).id, 'date_from': date_from, 'date_to': date_to})

    def _monto(self, recibo, xmlid):
        """Valor de UNA regla calculado con el motor (mismo patrón de tests/test_provisiones_periodo.py)."""
        regla = self.env.ref('l10n_co_nomina_electronica.%s' % xmlid)
        return regla._compute_rule({'payslip': recibo, 'contract': recibo.contract_id, 'result_rules': {}})[0]

    def _lineas(self, recibo, *lineas):
        """Crea líneas sintéticas (código, total) con la regla de la estructura del recibo (patrón de tests/test_desglose_recibo.py)."""
        for codigo, total in lineas:
            # active_test=False: CO_PRIMA_SALUD y CO_PRIMA_PENSION vienen archivadas (la prima no cotiza salud ni pensión, special_data.xml:142 y
            # :167) y el desglose de .284 las incluía en su lista de códigos: la equivalencia las cubre también.
            regla = self.env['hr.salary.rule'].with_context(active_test=False).search(
                [('code', '=', codigo), ('struct_id', '=', recibo.struct_id.id)], limit=1)
            self.assertTrue(regla, 'Falta la regla %s en %s' % (codigo, recibo.struct_id.name))
            self.env['hr.payslip.line'].create({
                'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': codigo, 'name': regla.name,
                'category_id': regla.category_id.id, 'contract_id': recibo.contract_id.id, 'employee_id': recibo.employee_id.id,
                'quantity': 1.0, 'rate': 100.0, 'amount': total, 'total': total})

    def _estructura(self, xmlid):
        return self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_' + xmlid)

    def _reglas_del_modulo(self, dominio):
        """Reglas que trae el módulo (con xmlid propio), no las que los usuarios hayan creado en la base donde corre la prueba."""
        datos = self.env['ir.model.data'].search([('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', 'hr.salary.rule')])
        return self.env['hr.salary.rule'].with_context(active_test=False).browse(datos.mapped('res_id')).exists().filtered_domain(dominio)

    def _antes(self, recibo, columna):
        """Lo que daba el código .284: suma por lista de códigos sobre las líneas que imprime la colilla."""
        return -sum(l.total for l in recibo._ne_pdf_lineas() if l.code in _DESGLOSE_ANTES[columna])

    # ── 1. tope del auxilio de transporte ────────────────────────────────────────────────────────────────────────────────────────
    def test_el_parametro_del_tope_existe_vale_2_y_cita_la_fuente(self):
        parametro = self.env.ref('l10n_co_nomina_electronica.rule_parameter_aux_transporte_tope_smmlv')
        self.assertEqual(parametro.code, _PARAMETRO_TOPE)
        for fecha in ('2024-01-01', '2025-06-30', '2026-06-01'):
            self.assertEqual(
                self.env['hr.rule.parameter']._get_parameter_from_code(_PARAMETRO_TOPE, fecha), 2, fecha)
        self.assertIn('Ley 1/1963', parametro.description)
        self.assertIn('pendiente de confirmar por David', parametro.description)

    def test_las_cuatro_formulas_leen_el_parametro_y_ya_no_el_literal_2(self):
        for codigo in _REGLAS_CON_TOPE:
            reglas = self._reglas_del_modulo([('code', '=', codigo)])
            self.assertTrue(reglas, codigo)
            for regla in reglas:
                texto = '\n'.join(
                    linea for linea in ('%s\n%s' % (regla.condition_python or '', regla.amount_python_compute or '')).splitlines()
                    if not linea.strip().startswith('#'))                       # sin comentarios: solo el código que se ejecuta
                self.assertIn(_PARAMETRO_TOPE, texto, '%s (%s)' % (codigo, regla.struct_id.name))
                self.assertIsNone(_LITERAL_DOS.search(texto), '%s (%s) aún multiplica por 2' % (codigo, regla.struct_id.name))

    def _provision(self, recibo, codigo):
        """.303: la provisión es lo que guarda la línea del recibo al calcular la hoja (la base sale de las líneas ya calculadas)."""
        recibo.compute_sheet()
        return sum(recibo.line_ids.filtered(lambda l: l.code == codigo).mapped('total'))

    def test_cambiar_el_tope_cambia_las_provisiones_que_suman_el_auxilio(self):
        """Sueldo 4.000.000: entre 2 y 3 SMMLV (2026). Con tope 2 no se paga auxilio y la base de prima/cesantías es el sueldo; con tope 3 la línea del auxilio se paga y suma.
        .303: la base sale de lo que paga la línea de CO_AUX_TRANS (que lee el tope), no del sueldo y el auxilio del contrato."""
        recibo = self._recibo(wage=4000000.0, name='Cambia el tope')
        smmlv = recibo._rule_parameter('l10n_co_smmlv', recibo.date_from)
        self.assertTrue(smmlv * 2 < recibo.contract_id.wage <= smmlv * 3, 'Premisa: sueldo entre 2 y 3 SMMLV')
        auxilio = recibo._rule_parameter('l10n_co_aux_transporte', recibo.date_from)
        codigos = ('CO_PROV_PRIMA', 'CO_PROV_CESANTIAS')
        for codigo in codigos:
            self.assertAlmostEqual(self._provision(recibo, codigo), 4000000.0 / 12, delta=0.01, msg='tope 2: %s' % codigo)
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': self.env.ref('l10n_co_nomina_electronica.rule_parameter_aux_transporte_tope_smmlv').id,
            'parameter_value': '3', 'date_from': date(2026, 1, 1)})
        for codigo in codigos:
            self.assertAlmostEqual(self._provision(recibo, codigo), (4000000.0 + auxilio) / 12, delta=0.01, msg='tope 3: %s' % codigo)

    def test_con_tope_2_decide_igual_que_el_literal_anterior_en_el_borde(self):
        """Exactamente 2 SMMLV (inclusive) suma el auxilio; un peso más, no. Mismo resultado que ``smmlv * 2`` de .284."""
        base = self._recibo(name='Borde base')
        smmlv = base._rule_parameter('l10n_co_smmlv', base.date_from)
        auxilio = base._rule_parameter('l10n_co_aux_transporte', base.date_from)
        for sueldo, suma_auxilio in ((smmlv, True), (smmlv * 2, True), (smmlv * 2 + 1, False)):
            recibo = self._recibo(wage=sueldo, name='Borde %s' % sueldo)
            esperado = (sueldo + (auxilio if sueldo <= smmlv * 2 else 0.0)) / 12.0
            self.assertEqual(sueldo <= smmlv * 2, suma_auxilio)
            self.assertAlmostEqual(self._provision(recibo, 'CO_PROV_PRIMA'), esperado, delta=0.01, msg='prima %s' % sueldo)
            self.assertAlmostEqual(self._provision(recibo, 'CO_PROV_CESANTIAS'), esperado, delta=0.01, msg='ces. %s' % sueldo)
            self.assertAlmostEqual(
                self._monto(recibo, 'hr_salary_rule_co_prima_base'), sueldo + (auxilio if suma_auxilio else 0.0), delta=0.005,
                msg='base de prima %s' % sueldo)

    # ── 2. desglose del recibo por concepto DIAN ─────────────────────────────────────────────────────────────────────────────────
    def test_las_reglas_con_concepto_dian_de_ley_son_exactamente_las_de_la_lista_anterior(self):
        for columna, concepto in _CONCEPTO_DE_COLUMNA.items():
            codigos = set(self._reglas_del_modulo([('l10n_co_ne_dian_concept', '=', concepto)]).mapped('code'))
            self.assertEqual(codigos, set(_DESGLOSE_ANTES[columna]), columna)
            self.assertEqual(self.env['hr.payslip']._NE_DESGLOSE_CONCEPTO_DIAN[columna], concepto)

    def test_el_desglose_es_igual_al_de_antes_en_un_recibo_con_salud_pension_fsp_retencion_y_deduccion_con_tercero(self):
        recibo = self._recibo(estructura=self._estructura('co_nomina'), name='Desglose general')
        self._lineas(
            recibo, ('CO_BASICO', 3000000.0), ('CO_AUX_TRANS', 200000.0), ('CO_SALUD_EMP', -120000.0), ('CO_PENSION_EMP', -120000.0),
            ('CO_FSP', -30000.0), ('CO_RETEFUENTE', -50000.0), ('CO_SINDICATO', -10000.0), ('CO_NETO', 2870000.0))
        d = recibo._ne_desglose()
        self.assertEqual((d['salud'], d['pension'], d['fsp'], d['retencion']), (120000.0, 120000.0, 30000.0, 50000.0))
        self.assertEqual(d['otras_deducciones'], 10000.0)                      # la deducción con tercero (sindicato) no es de ley
        self.assertEqual((d['devengado'], d['deducciones'], d['neto'], d['diferencia']), (3200000.0, 330000.0, 2870000.0, 0.0))
        for columna in _DESGLOSE_ANTES:
            self.assertEqual(d[columna], self._antes(recibo, columna), columna)

    def test_el_desglose_es_igual_al_de_antes_en_prima_liquidacion_y_bonificacion(self):
        casos = (
            ('co_prima', (('CO_PRIMA_VALOR', 1500000.0), ('CO_PRIMA_SALUD', -60000.0), ('CO_PRIMA_PENSION', -60000.0),
                          ('CO_PRIMA_RETE', -30000.0), ('CO_PRIMA_NETO', 1350000.0))),
            ('co_liquidacion', (('CO_LIQ_SALARIOS', 900000.0), ('CO_LIQ_SALUD', -36000.0), ('CO_LIQ_PENSION', -36000.0),
                                ('CO_LIQ_RETE', -10000.0), ('CO_LIQ_NETO', 818000.0))),
            ('co_bonificacion', (('CO_BON_VALOR', 500000.0), ('CO_BON_SALUD', -20000.0), ('CO_BON_PENSION', -20000.0),
                                 ('CO_BON_RETE', -5000.0), ('CO_BON_NETO', 455000.0))),
        )
        for estructura, lineas in casos:
            recibo = self._recibo(estructura=self._estructura(estructura), name='Desglose %s' % estructura)
            self._lineas(recibo, *lineas)
            d = recibo._ne_desglose()
            for columna in _DESGLOSE_ANTES:
                self.assertEqual(d[columna], self._antes(recibo, columna), '%s %s' % (estructura, columna))
            self.assertEqual(d['diferencia'], 0.0, estructura)

    def test_el_desglose_sigue_el_concepto_dian_configurado_en_la_regla(self):
        """Lo que ahora es configuración: si la empresa marca una regla como «Salud», su valor cae en la columna de salud."""
        recibo = self._recibo(estructura=self._estructura('co_nomina'), name='Desglose configurado')
        self._lineas(recibo, ('CO_BASICO', 3000000.0), ('CO_SALUD_EMP', -120000.0), ('CO_EMBARGO', -200000.0), ('CO_NETO', 2680000.0))
        antes = recibo._ne_desglose()
        self.assertEqual((antes['salud'], antes['otras_deducciones']), (120000.0, 200000.0))
        embargo = self.env['hr.salary.rule'].search([('code', '=', 'CO_EMBARGO'), ('struct_id', '=', recibo.struct_id.id)], limit=1)
        embargo.l10n_co_ne_dian_concept = 'Salud'
        despues = recibo._ne_desglose()
        self.assertEqual((despues['salud'], despues['otras_deducciones']), (320000.0, 0.0))
        self.assertEqual(despues['deducciones'], antes['deducciones'])         # el total no cambia: solo la columna

    # ── 3. tercero de las deducciones del contrato ───────────────────────────────────────────────────────────────────────────────
    def test_cada_regla_anterior_declara_su_origen_y_apunta_al_mismo_campo_del_contrato(self):
        for codigo, campo in _TERCERO_ANTES.items():
            reglas = self._reglas_del_modulo([('code', '=', codigo)])
            self.assertTrue(reglas, codigo)
            for regla in reglas:
                origen = regla.l10n_co_tercero_origen
                self.assertTrue(origen, '%s (%s) sin origen de tercero' % (codigo, regla.struct_id.name))
                self.assertEqual(self.env['hr.payslip']._NE_TERCERO_ORIGEN_CAMPO[origen], ('contract_id', campo), codigo)

    def test_la_deduccion_sin_tercero_en_el_contrato_da_el_mismo_error_de_antes_para_las_seis(self):
        for codigo, campo in _TERCERO_ANTES.items():
            recibo = self._recibo(estructura=self.est_general, name='Tercero %s' % codigo)
            self._lineas(recibo, (codigo, -50000.0))
            with self.assertRaises(UserError) as error:
                recibo._ne_validar_terceros_deducciones()
            self.assertIn(recibo.contract_id._fields[campo].string, str(error.exception), codigo)
            self.assertIn(recibo.contract_id.display_name, str(error.exception), codigo)
            recibo.contract_id[campo] = self.env['res.partner'].create({'name': 'Entidad %s' % codigo, 'l10n_co_entity_type': 'other'})
            recibo._ne_validar_terceros_deducciones()                          # con el contacto del contrato pasa

    def test_sin_origen_de_contrato_o_con_valor_cero_no_exige_tercero(self):
        recibo = self._recibo(estructura=self.est_general, name='Sin tercero')
        self._lineas(recibo, ('CO_SALUD_EMP', -120000.0), ('CO_SINDICATO', 0.0))
        recibo._ne_validar_terceros_deducciones()

    def test_una_regla_con_origen_de_contrato_configurado_tambien_se_valida(self):
        """Lo que ahora es configuración: el origen de la regla decide, no su código."""
        recibo = self._recibo(estructura=self.est_general, name='Tercero configurado')
        salud = self.env['hr.salary.rule'].search([('code', '=', 'CO_SALUD_EMP'), ('struct_id', '=', recibo.struct_id.id)], limit=1)
        self._lineas(recibo, ('CO_SALUD_EMP', -120000.0))
        recibo._ne_validar_terceros_deducciones()                              # origen EPS del empleado: no es del contrato
        salud.l10n_co_tercero_origen = 'contract_afc'
        with self.assertRaises(UserError) as error:
            recibo._ne_validar_terceros_deducciones()
        self.assertIn(recibo.contract_id._fields['l10n_co_ne_afc_partner_id'].string, str(error.exception))

    # ── 4. código muerto ─────────────────────────────────────────────────────────────────────────────────────────────────────────
    def test_ya_no_existe_la_copia_defensiva_del_mapa_de_ausencias(self):
        self.assertNotIn('local_map', inspect.getsource(HrPayslip._get_overlapping_leaves_data))
        modelo = self.env['hr.payslip']
        self.assertEqual(modelo._LEAVE_CODE_MAP['CO_INC_COMUN'], 'incapacidad')   # el mapa real del mixin sigue ahí
        self.assertEqual(modelo._LEAVE_CODE_MAP['CO_LIC_NR'], 'licencia_nr')
