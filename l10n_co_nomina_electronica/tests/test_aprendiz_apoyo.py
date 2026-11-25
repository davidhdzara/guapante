# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""H-F1-09 (doc 88, diseño aprobado por el TL el 24-nov; D1-D3): el apoyo de sostenimiento del aprendiz ES el sueldo de su contrato (única fuente). La etapa (``l10n_co_aprendiz_etapas``) decide qué regla lo paga, qué
causa y qué se provisiona; ya no hay novedad. Antes, con sueldo 0 y la novedad, la prima y las cesantías salían solo sobre el auxilio, las vacaciones en 0 y el XML sin ``Basico``; con sueldo = apoyo y la novedad se
pagaba dos veces (QA, f1_j y f1_j2). Incluye los controles de que quien NO es aprendiz recibe los mismos valores que antes.

Contrato desde el 2026-01-01. Nómina: marzo de 2026. Prima: julio-diciembre. Liquidación: retiro el 2026-08-15."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

INICIO = date(2026, 1, 1)
RETIRO = date(2026, 8, 15)
MARZO = (date(2026, 3, 1), date(2026, 3, 31))
PROVISIONES = ('CO_PROV_PRIMA', 'CO_PROV_CESANTIAS', 'CO_PROV_INT_CES', 'CO_PROV_VACACIONES')
APOYOS = ('CO_APOYO_SOST', 'CO_APOYO_SOST_PRAC')
# (nombre, tipo de cotizante, tipo de contrato, regla que paga el apoyo, fracción del SMMLV)
LECTIVA = ('Apoyo Lectiva', '19', '4', 'CO_APOYO_SOST', 0.75)
PRACTICA = ('Apoyo Practica', '01', '4', 'CO_APOYO_SOST_PRAC', 1.0)


@tagged('post_install', '-at_install')
class TestAprendizApoyo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Apoyo del Aprendiz'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'Prueba Estructura Apoyo', 'country_id': cls.env.ref('base.co').id})
        cls.general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.prima = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.liquidacion = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})

    def _parametro(self, codigo, fecha=MARZO[0]):
        return self.env['hr.rule.parameter']._get_parameter_from_code(codigo, fecha)

    def _contrato(self, nombre, tipo, tipo_contrato, sueldo):
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': nombre, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        return self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': tipo_contrato, 'l10n_co_pila_tipo_cotizante': tipo, 'l10n_co_pila_subtipo_cotizante': '00', 'name': 'Contrato %s' % nombre,
            'employee_id': empleado.id, 'company_id': self.company.id, 'structure_type_id': self.structure_type.id, 'wage': sueldo, 'date_start': INICIO, 'state': 'open'})

    def _aprendiz(self, caso, sufijo=''):
        nombre, tipo, tipo_contrato, _regla, fraccion = caso
        return self._contrato(nombre + sufijo, tipo, tipo_contrato, fraccion * self._parametro('l10n_co_smmlv'))

    def _recibo(self, contrato, estructura, desde, hasta, calcular=True):
        contrato.generate_work_entries(INICIO if estructura == self.liquidacion else desde, hasta)
        recibo = self.env['hr.payslip'].create({
            'name': '%s %s %s' % (estructura.name, contrato.name, desde), 'employee_id': contrato.employee_id.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': estructura.id, 'date_from': desde, 'date_to': hasta})
        if calcular:
            recibo.compute_sheet()
        return recibo

    def _linea(self, recibo, codigo):
        return recibo.line_ids.filtered(lambda l: l.code == codigo)

    def _valor(self, recibo, codigo):
        linea = self._linea(recibo, codigo)
        self.assertEqual(len(linea), 1, codigo)
        return linea.total

    def _devengados(self, recibo):
        return recibo._build_devengados(recibo._group_lines_by_concept())

    def _ausencia(self, contrato, xmlid, desde, hasta):
        contrato.generate_work_entries(MARZO[0], MARZO[1])
        ausencia = self.env['hr.leave'].create({
            'employee_id': contrato.employee_id.id, 'holiday_status_id': self.env.ref('l10n_co_nomina_electronica.%s' % xmlid).id,
            'request_date_from': desde, 'request_date_to': hasta})
        ausencia.action_validate()
        self.assertEqual(ausencia.state, 'validate')

    # ── el apoyo es el sueldo del contrato ──
    def test_la_nomina_paga_el_apoyo_del_sueldo_del_contrato_por_los_dias_y_el_basico_queda_en_cero(self):
        for caso in (LECTIVA, PRACTICA):
            codigo = caso[3]
            for desde, hasta, dias in ((date(2026, 3, 1), date(2026, 3, 31), 30), (date(2026, 4, 1), date(2026, 4, 15), 15)):
                contrato = self._aprendiz(caso, ' %s dias' % dias)
                recibo = self._recibo(contrato, self.general, desde, hasta)
                linea = self._linea(recibo, codigo)
                self.assertEqual(linea.quantity, dias, caso[0])
                self.assertAlmostEqual(linea.total, contrato.wage / 30 * dias, delta=0.01, msg=caso[0])
                self.assertFalse(self._linea(recibo, [c for c in APOYOS if c != codigo][0]), caso[0])
                basico = self._linea(recibo, 'CO_BASICO')
                self.assertEqual((basico.total, basico.quantity), (0.0, dias), caso[0])

    def test_la_practica_provisiona_sobre_el_apoyo_y_la_lectiva_no_provisiona(self):
        practica = self._recibo(self._aprendiz(PRACTICA), self.general, *MARZO)
        apoyo, auxilio = practica.contract_id.wage, self._parametro('l10n_co_aux_transporte')
        cesantias = (apoyo + auxilio) / 12
        self.assertAlmostEqual(self._valor(practica, 'CO_PROV_PRIMA'), cesantias, delta=0.01)          # apoyo + auxilio
        self.assertAlmostEqual(self._valor(practica, 'CO_PROV_CESANTIAS'), cesantias, delta=0.01)
        self.assertAlmostEqual(self._valor(practica, 'CO_PROV_INT_CES'), cesantias * self._parametro('l10n_co_pct_intereses_cesantias') / 100, delta=0.01)
        self.assertAlmostEqual(self._valor(practica, 'CO_PROV_VACACIONES'), apoyo * 30 / 720, delta=0.01)      # sin auxilio (CST art. 192)
        lectiva = self._recibo(self._aprendiz(LECTIVA), self.general, *MARZO)
        for codigo in PROVISIONES:
            self.assertFalse(self._linea(lectiva, codigo), codigo)

    def test_vacaciones_y_licencia_remunerada_del_practicante_se_pagan_sobre_el_apoyo_y_sin_aviso_de_ibc(self):
        """Dato de QA: con sueldo 0 salían en 0. El control: a un dependiente sin mes anterior el aviso le sigue saliendo."""
        practica = self._aprendiz(PRACTICA)
        dependiente = self._contrato('Dependiente Con Ausencias', '01', '2', 3000000.0)
        for contrato in (practica, dependiente):
            self._ausencia(contrato, 'hr_leave_type_co_vac', date(2026, 3, 2), date(2026, 3, 6))
            self._ausencia(contrato, 'hr_leave_type_co_lic_rem', date(2026, 3, 9), date(2026, 3, 13))
        recibo = self._recibo(practica, self.general, *MARZO)
        for codigo in ('CO_VAC', 'CO_LIC_REM'):
            self.assertAlmostEqual(self._valor(recibo, codigo), practica.wage / 30 * 5, delta=0.01, msg=codigo)
        self.assertEqual(self._linea(recibo, 'CO_APOYO_SOST_PRAC').quantity, 20)
        self.assertNotIn('No hay IBC del mes anterior', recibo.l10n_co_ne_aviso_ibc_anterior or '')
        control = self._recibo(dependiente, self.general, *MARZO)
        self.assertAlmostEqual(self._valor(control, 'CO_VAC'), 3000000.0 / 30 * 5, delta=0.01)
        self.assertIn('No hay IBC del mes anterior', control.l10n_co_ne_aviso_ibc_anterior or '')

    def test_la_practica_liquida_el_apoyo_pendiente_y_las_prestaciones_sobre_el_apoyo(self):
        recibo = self._recibo(self._aprendiz(PRACTICA), self.liquidacion, INICIO, RETIRO)
        apoyo, auxilio = recibo.contract_id.wage, self._parametro('l10n_co_aux_transporte', RETIRO)
        self.assertAlmostEqual(self._valor(recibo, 'CO_APOYO_SOST_PRAC'), apoyo / 30 * 15, delta=0.01)
        self.assertEqual(self._valor(recibo, 'CO_LIQ_SALARIOS'), 0.0)
        for codigo in ('CO_LIQ_PRIMA', 'CO_LIQ_CESANTIAS'):
            linea = self._linea(recibo, codigo)
            self.assertAlmostEqual(linea.total * 360 / linea.quantity, apoyo + auxilio, delta=1.0, msg=codigo)
        self.assertAlmostEqual(self._linea(recibo, 'CO_LIQ_VACACIONES').amount, apoyo / 30, delta=0.01)      # vacaciones sobre el apoyo, sin auxilio
        prima = self._recibo(self._aprendiz(PRACTICA, ' prima'), self.prima, date(2026, 7, 1), date(2026, 12, 31))
        self.assertAlmostEqual(self._valor(prima, 'CO_PRIMA_VALOR'), (apoyo + auxilio) / 2, delta=0.01)

    # ── quien no es aprendiz: los mismos valores ──
    def test_el_dependiente_conserva_sus_valores_en_nomina_provisiones_prima_liquidacion_y_xml(self):
        sueldo = 3000000.0
        auxilio = self._parametro('l10n_co_aux_transporte')
        nomina = self._recibo(self._contrato('Control Nomina', '01', '2', sueldo), self.general, *MARZO)
        self.assertEqual((self._valor(nomina, 'CO_BASICO'), self._linea(nomina, 'CO_BASICO').quantity), (sueldo, 30))
        self.assertAlmostEqual(self._valor(nomina, 'CO_AUX_TRANS'), auxilio, delta=0.01)
        for codigo in APOYOS:
            self.assertFalse(self._linea(nomina, codigo), codigo)
        cesantias = (sueldo + auxilio) / 12
        for codigo, esperado in (('CO_PROV_PRIMA', cesantias), ('CO_PROV_CESANTIAS', cesantias),
                                 ('CO_PROV_INT_CES', cesantias * self._parametro('l10n_co_pct_intereses_cesantias') / 100), ('CO_PROV_VACACIONES', sueldo * 30 / 720)):
            self.assertAlmostEqual(self._valor(nomina, codigo), esperado, delta=0.01, msg=codigo)
        devengados = self._devengados(nomina)
        self.assertEqual(devengados['Basico'], {'DiasTrabajados': '30', 'SueldoTrabajado': '3000000.00'})
        self.assertNotIn('ApoyoSost', devengados)
        prima = self._recibo(self._contrato('Control Prima', '01', '2', sueldo), self.prima, date(2026, 7, 1), date(2026, 12, 31))
        self.assertAlmostEqual(self._valor(prima, 'CO_PRIMA_VALOR'), (sueldo + auxilio) / 2, delta=0.01)
        liquidacion = self._recibo(self._contrato('Control Liquidacion', '01', '2', sueldo), self.liquidacion, INICIO, RETIRO)
        self.assertAlmostEqual(self._valor(liquidacion, 'CO_LIQ_SALARIOS'), sueldo / 30 * 15, delta=0.01)
        for codigo in ('CO_LIQ_PRIMA', 'CO_LIQ_CESANTIAS'):
            linea = self._linea(liquidacion, codigo)
            self.assertAlmostEqual(linea.total * 360 / linea.quantity, sueldo + auxilio, delta=1.0, msg=codigo)
        for codigo in APOYOS:
            self.assertFalse(self._linea(liquidacion, codigo), codigo)

    # ── XML ──
    def test_el_xml_del_aprendiz_lleva_basico_en_cero_con_sus_dias_y_el_apoyo_y_la_prima_no_suma_dias(self):
        recibo = self._recibo(self._aprendiz(PRACTICA), self.general, *MARZO)
        devengados = self._devengados(recibo)
        self.assertEqual(devengados['Basico'], {'DiasTrabajados': '30', 'SueldoTrabajado': '0.00'})
        self.assertIn('ApoyoSost', devengados)
        prima = self._recibo(self._aprendiz(PRACTICA, ' xml prima'), self.prima, date(2026, 7, 1), date(2026, 12, 31))
        self.assertNotIn('Basico', self._devengados(prima))

    # ── datos que faltan: error claro ──
    def test_el_aprendiz_con_sueldo_cero_no_se_calcula_en_nomina_prima_ni_liquidacion(self):
        for estructura, desde, hasta in ((self.general,) + MARZO, (self.prima, date(2026, 7, 1), date(2026, 12, 31)), (self.liquidacion, INICIO, RETIRO)):
            nombre = 'Sin Apoyo %s' % estructura.id
            recibo = self._recibo(self._contrato(nombre, '01', '4', 0.0), estructura, desde, hasta, calcular=False)
            with self.assertRaisesRegex(UserError, 'tiene el sueldo en 0') as caso:
                recibo.compute_sheet()
            self.assertIn(nombre, str(caso.exception), estructura.name)

    def test_la_novedad_del_apoyo_ya_no_se_ofrece(self):
        tipo = self.env.ref('l10n_co_nomina_electronica.input_co_apoyo_sost')
        self.assertFalse(tipo.active)
        for regla in self.env['hr.salary.rule'].search([('code', 'in', APOYOS)]):
            self.assertFalse(regla.l10n_co_ne_alimentada_por_novedad, '%s %s' % (regla.code, regla.struct_id.name))

    # ── un contrato por etapa (D3) ──
    def _gestor_de_contratos(self):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Gestor de Contratos Apoyo', 'login': 'gestor_contratos_apoyo', 'email': 'gestor_contratos_apoyo@example.com', 'company_id': self.company.id,
            'company_ids': [(6, 0, self.company.ids)],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('hr_contract.group_hr_contract_manager').id])]})

    def test_un_contrato_con_recibos_confirmados_de_lectiva_no_pasa_a_practica_ni_para_quien_no_ve_nomina(self):
        contrato = self._aprendiz(LECTIVA, ' cambio')
        self._recibo(contrato, self.general, *MARZO).write({'state': 'done'})
        gestor = self._gestor_de_contratos()
        self.assertFalse(gestor.has_group('hr_payroll.group_hr_payroll_user'))
        for quien in (contrato, contrato.with_user(gestor)):
            with self.assertRaisesRegex(UserError, 'cree el de la práctica'):
                quien.write({'l10n_co_pila_tipo_cotizante': '01'})
        self.assertEqual(contrato.l10n_co_pila_tipo_cotizante, '19')

    def test_los_demas_cambios_de_tipo_se_permiten(self):
        sin_recibos = self._aprendiz(LECTIVA, ' sin recibos')
        sin_recibos.write({'l10n_co_pila_tipo_cotizante': '01'})
        self.assertEqual(sin_recibos.l10n_co_pila_tipo_cotizante, '01')
        practica = self._aprendiz(PRACTICA, ' a lectiva')
        self._recibo(practica, self.general, *MARZO).write({'state': 'done'})
        practica.write({'l10n_co_pila_tipo_cotizante': '19'})
        dependiente = self._contrato('Cambio Dependiente', '01', '2', 3000000.0)
        self._recibo(dependiente, self.general, *MARZO).write({'state': 'done'})
        dependiente.with_user(self._gestor_de_contratos()).write({'l10n_co_ne_contract_type': '1'})
        self.assertEqual(dependiente.l10n_co_ne_contract_type, '1')
