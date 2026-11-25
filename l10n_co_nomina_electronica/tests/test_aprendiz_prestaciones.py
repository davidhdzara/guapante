# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-12 (doc 88, diseno aprobado por el TL el 24-nov): las estructuras de PRIMA y de LIQUIDACION no leian la etapa del aprendiz. En la etapa lectiva no hay prima, cesantias, intereses ni vacaciones (Decreto 223/2026
art. 2.2.6.3.3.6 num. 1; Circular MinTrabajo 083/2025 num. 4) y la base no suma auxilio de transporte; la practica, la dual y el que no es aprendiz no cambian. Las dos decisiones salen de
``HrPayslip._ne_regimen_cotizante`` (parametro ``l10n_co_aprendiz_etapas``: columnas «paga auxilio de transporte» y «causa prestaciones»). D1: con vacaciones validadas en el ultimo tramo, error (ocultar la linea
dejaria sin pagar dias que se restan del sueldo). En ejecucion sobre .321 (QA, f1_i): la lectiva sumaba el auxilio en la base y traia todas las lineas.

Contrato desde el 2026-01-01 con sueldo de 1 SMMLV (bajo el tope del auxilio). Prima: julio-diciembre de 2026 (180 dias). Liquidacion: retiro el 2026-08-15."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.misc import format_date

INICIO = date(2026, 1, 1)
RETIRO = date(2026, 8, 15)
SIN_LINEA_EN_PRIMA = ('CO_PRIMA_VALOR', 'CO_PRIMA_RETE')
PRESTACIONES_DE_LIQUIDACION = ('CO_LIQ_PRIMA', 'CO_LIQ_CESANTIAS', 'CO_LIQ_INT_CES', 'CO_LIQ_VACACIONES')
REGLAS_CON_LA_DECISION = ('CO_PRIMA_VALOR', 'CO_LIQ_PRIMA', 'CO_LIQ_CESANTIAS', 'CO_LIQ_VACACIONES')
REGLAS_CON_AUXILIO = ('CO_AUX_TRANS', 'CO_PRIMA_BASE', 'CO_LIQ_PRIMA', 'CO_LIQ_CESANTIAS')
# (nombre, tipo de cotizante, tipo de contrato)
LECTIVA = ('Lectiva', '19', '4')
CON_PRESTACIONES = (('Practica o dual', '01', '4'), ('Dependiente', '01', '2'))


@tagged('post_install', '-at_install')
class TestAprendizPrestaciones(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Prestaciones del Aprendiz'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'Prueba Estructura Prestaciones Aprendiz', 'country_id': cls.env.ref('base.co').id})
        cls.prima = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.liquidacion = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.vacaciones = cls.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_vac')
        cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})

    def _contrato(self, nombre, tipo, tipo_contrato):
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': nombre, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        sueldo = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_co_smmlv', RETIRO)
        return self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': tipo_contrato, 'l10n_co_pila_tipo_cotizante': tipo, 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato %s' % nombre,
            'employee_id': empleado.id, 'company_id': self.company.id, 'structure_type_id': self.structure_type.id, 'wage': sueldo, 'date_start': INICIO, 'state': 'open'})

    def _recibo(self, contrato, estructura, desde, hasta):
        return self.env['hr.payslip'].create({
            'name': '%s %s' % (estructura.name, contrato.name), 'employee_id': contrato.employee_id.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': estructura.id, 'date_from': desde, 'date_to': hasta})

    def _de_prima(self, nombre, tipo, tipo_contrato):
        recibo = self._recibo(self._contrato(nombre, tipo, tipo_contrato), self.prima, date(2026, 7, 1), date(2026, 12, 31))
        recibo.compute_sheet()
        return recibo

    def _de_liquidacion(self, nombre, tipo, tipo_contrato, vacaciones=None, calcular=True):
        contrato = self._contrato(nombre, tipo, tipo_contrato)
        contrato.generate_work_entries(INICIO, RETIRO)
        if vacaciones:
            ausencia = self.env['hr.leave'].create({
                'employee_id': contrato.employee_id.id, 'holiday_status_id': self.vacaciones.id,
                'request_date_from': vacaciones[0], 'request_date_to': vacaciones[1]})
            ausencia.action_validate()
            self.assertEqual(ausencia.state, 'validate')
        recibo = self._recibo(contrato, self.liquidacion, INICIO, RETIRO)
        if calcular:
            recibo.compute_sheet()
        return recibo

    def _linea(self, recibo, codigo):
        return recibo.line_ids.filtered(lambda l: l.code == codigo)

    def _valores(self, recibo):
        fecha = recibo._ne_fecha_parametros()
        return (recibo._rule_parameter('l10n_co_smmlv', fecha), recibo._rule_parameter('l10n_co_aux_transporte', fecha),
                recibo._rule_parameter('l10n_co_dias_anio_comercial', fecha))

    def _base_de(self, recibo, codigo):
        """Base con la que se pago una prestacion: total x dias del anio comercial / dias de la linea."""
        linea = self._linea(recibo, codigo)
        self.assertTrue(linea.quantity, codigo)
        return linea.total * self._valores(recibo)[2] / linea.quantity

    # ── etapa lectiva ──
    def test_la_lectiva_no_tiene_linea_de_prima_y_la_base_no_suma_el_auxilio(self):
        recibo = self._de_prima(*LECTIVA)
        smmlv, _auxilio, _dias = self._valores(recibo)
        for codigo in SIN_LINEA_EN_PRIMA:
            self.assertFalse(self._linea(recibo, codigo), codigo)
        self.assertAlmostEqual(self._linea(recibo, 'CO_PRIMA_BASE').total, smmlv, delta=0.01)       # linea interna (no impresa): el sueldo, sin auxilio
        self.assertEqual(self._linea(recibo, 'CO_PRIMA_NETO').total, 0.0)

    def test_la_lectiva_liquida_solo_el_sueldo_sin_prima_cesantias_intereses_ni_vacaciones(self):
        recibo = self._de_liquidacion(*LECTIVA)
        for codigo in PRESTACIONES_DE_LIQUIDACION + ('CO_LIQ_VAC_DISFRUTADAS',):
            self.assertFalse(self._linea(recibo, codigo), codigo)
        salarios = self._linea(recibo, 'CO_LIQ_SALARIOS')
        self.assertTrue(salarios.total)
        self.assertAlmostEqual(self._linea(recibo, 'CO_LIQ_NETO').total, salarios.total, delta=0.01)

    # ── practica, dual y dependiente: sin cambio ──
    def test_la_practica_y_el_dependiente_siguen_con_la_prima_sobre_sueldo_mas_auxilio(self):
        for nombre, tipo, tipo_contrato in CON_PRESTACIONES:
            recibo = self._de_prima(nombre, tipo, tipo_contrato)
            smmlv, auxilio, _dias = self._valores(recibo)
            self.assertAlmostEqual(self._linea(recibo, 'CO_PRIMA_BASE').total, smmlv + auxilio, delta=0.01, msg=nombre)
            self.assertAlmostEqual(self._linea(recibo, 'CO_PRIMA_VALOR').total, (smmlv + auxilio) / 2, delta=0.01, msg=nombre)      # semestre completo
            self.assertTrue(self._linea(recibo, 'CO_PRIMA_RETE'), nombre)

    def test_la_practica_y_el_dependiente_siguen_con_las_prestaciones_de_la_liquidacion(self):
        for nombre, tipo, tipo_contrato in CON_PRESTACIONES:
            recibo = self._de_liquidacion(nombre, tipo, tipo_contrato)
            smmlv, auxilio, _dias = self._valores(recibo)
            for codigo in PRESTACIONES_DE_LIQUIDACION:
                self.assertTrue(self._linea(recibo, codigo).total, '%s %s' % (nombre, codigo))
            for codigo in ('CO_LIQ_PRIMA', 'CO_LIQ_CESANTIAS'):
                self.assertAlmostEqual(self._base_de(recibo, codigo), smmlv + auxilio, delta=1.0, msg='%s %s' % (nombre, codigo))

    # ── el parametro manda: las dos columnas, por separado ──
    def test_un_valor_nuevo_del_parametro_devuelve_las_prestaciones_sin_tocar_codigo_y_sin_auxilio(self):
        """La lectiva con «causa prestaciones» encendida y «paga auxilio» apagado: salen las lineas y su base es el sueldo."""
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': self.env.ref('l10n_co_nomina_electronica.rule_parameter_aprendiz_etapas').id, 'date_from': date(2026, 7, 1),
            'parameter_value': "[('19', '*', 'lectiva', '12', False, True), ('01', '4', 'practica', '19', True, True)]"})
        prima = self._de_prima('Lectiva Con Prima', '19', '4')
        smmlv = self._valores(prima)[0]
        self.assertAlmostEqual(self._linea(prima, 'CO_PRIMA_VALOR').total, smmlv / 2, delta=0.01)
        liquidacion = self._de_liquidacion('Lectiva Con Prestaciones', '19', '4')
        for codigo in PRESTACIONES_DE_LIQUIDACION:
            self.assertTrue(self._linea(liquidacion, codigo).total, codigo)
        for codigo in ('CO_LIQ_PRIMA', 'CO_LIQ_CESANTIAS'):
            self.assertAlmostEqual(self._base_de(liquidacion, codigo), smmlv, delta=1.0, msg=codigo)

    # ── D1: vacaciones validadas en el ultimo tramo ──
    def test_la_lectiva_con_vacaciones_en_el_ultimo_tramo_da_un_error_que_nombra_empleado_y_ausencia(self):
        recibo = self._de_liquidacion('Lectiva Con Vacaciones', '19', '4', vacaciones=(date(2026, 8, 3), date(2026, 8, 7)), calcular=False)
        with self.assertRaises(UserError) as caso:
            recibo.compute_sheet()
        texto = str(caso.exception)
        for esperado in ('no causa vacaciones', 'Lectiva Con Vacaciones', self.vacaciones.name, format_date(recibo.env, date(2026, 8, 3)),
                         format_date(recibo.env, date(2026, 8, 7)), 'l10n_co_aprendiz_etapas'):
            self.assertIn(esperado, texto)

    def test_la_lectiva_con_vacaciones_de_un_mes_anterior_no_da_error_ni_linea(self):
        recibo = self._de_liquidacion('Lectiva Vacaciones Marzo', '19', '4', vacaciones=(date(2026, 3, 2), date(2026, 3, 6)))
        self.assertFalse(self._linea(recibo, 'CO_LIQ_VAC_DISFRUTADAS'))
        self.assertTrue(self._linea(recibo, 'CO_LIQ_SALARIOS').total)

    def test_la_practica_con_vacaciones_en_el_ultimo_tramo_las_sigue_pagando(self):
        recibo = self._de_liquidacion('Practica Con Vacaciones', '01', '4', vacaciones=(date(2026, 8, 3), date(2026, 8, 7)))
        self.assertEqual(self._linea(recibo, 'CO_LIQ_VAC_DISFRUTADAS').quantity, 5.0)

    # ── una sola decision ──
    def test_las_formulas_consultan_el_metodo_y_ninguna_compara_la_etapa(self):
        datos = self.env['ir.model.data'].search([('module', '=', 'l10n_co_nomina_electronica'), ('model', '=', 'hr.salary.rule')])
        reglas = self.env['hr.salary.rule'].browse(datos.mapped('res_id')).exists()
        for codigos, clave in ((REGLAS_CON_LA_DECISION, 'causa_prestaciones'), (REGLAS_CON_AUXILIO, 'paga_auxilio_transporte')):
            for codigo in codigos:
                regla = reglas.filtered(lambda r: r.code == codigo)
                self.assertEqual(len(regla), 1, codigo)
                texto = '\n'.join(
                    linea for linea in ('%s\n%s' % (regla.condition_python or '', regla.amount_python_compute or '')).splitlines()
                    if not linea.strip().startswith('#'))
                self.assertIn("_ne_regimen_cotizante()['%s']" % clave, texto, codigo)
                self.assertNotIn('lectiva', texto, codigo)
                self.assertNotIn('practica', texto, codigo)
        self.assertEqual(reglas.filtered(lambda r: r.code == 'CO_LIQ_VACACIONES').condition_select, 'python')
