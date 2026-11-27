# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""PILA con más de un recibo por empleado en el mes (.330, hallazgo del TL): el encabezado (registro tipo 1) y el resumen de la validación cuentan COTIZANTES, no recibos, y los totales del resumen son
los de los registros tipo 2 (el IBC del mes una sola vez). Fixture: un empleado con las dos quincenas de septiembre y otro con una sola; los valores esperados salen a mano del salario."""

import base64
from datetime import date

from odoo.addons.l10n_co_nomina_electronica.services import pila_generator_v2
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged

from .test_pila_ubicacion_laboral import direccion_de_trabajo, ubicaciones_de_prueba

SALARIO = 3000000.0          # con 16 % de pensión (empleado + empleador): 480.000 el mes completo y 240.000 una quincena


@tagged('post_install', '-at_install')
class TestPilaCotizantesPorEmpleado(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        cls.entidades = {
            tipo: Partner.create({'name': '%s Cotizantes' % tipo.upper(), 'l10n_co_entity_type': tipo, 'l10n_co_pila_entity_code': codigo})
            for tipo, codigo in (('eps', 'EPS778'), ('afp', 'AFP778'), ('ccf', 'CCF778'), ('arl', '14-78'))}
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1',
            'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Cotizantes PILA', 'l10n_co_pila_ccf_por_empleado': True,
            'l10n_co_pila_arl_id': cls.entidades['arl'].id, 'l10n_co_pila_operador_code': '89'})
        cls.env = cls.company.with_company(cls.company).env
        (departamento, ciudad), = ubicaciones_de_prueba(cls.env, 1)
        cls.company.partner_id.with_context(no_vat_validation=True).write({'vat': '900123456-8'})
        cls.lugar = direccion_de_trabajo(cls.env, 'Sede Cotizantes PILA', departamento, ciudad)
        cls.tipo_quincenal = cls.env['hr.payroll.structure.type'].create({
            'name': 'Cotizantes PILA quincenal', 'country_id': cls.env.ref('base.co').id, 'default_schedule_pay': 'semi-monthly'})
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.env['l10n.co.retefuente.uvt'].create({'year': '2026', 'company_id': cls.company.id, 'procedure': '1'})

    def _contrato(self, nombre, documento, desde=date(2024, 1, 1), **contrato):
        empleado = self.env['hr.employee'].create({
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 'name': nombre, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10',
            'identification_id': documento, 'l10n_co_primer_nombre': nombre, 'l10n_co_primer_apellido': 'Prueba', 'address_id': self.lugar.id,
            'l10n_co_pila_eps_id': self.entidades['eps'].id, 'l10n_co_pila_afp_id': self.entidades['afp'].id, 'l10n_co_pila_ccf_id': self.entidades['ccf'].id})
        return self._contrato_de(empleado, desde=desde, **contrato)

    def _contrato_de(self, empleado, salario=SALARIO, desde=date(2024, 1, 1), tipo='01', tipo_contrato='2'):
        contrato = self.env['hr.contract'].create({
            'l10n_co_ne_contract_type': tipo_contrato, 'l10n_co_pila_tipo_cotizante': tipo, 'l10n_co_pila_subtipo_cotizante': '00', 'l10n_co_pila_centro_trabajo': '1',
            'name': 'Contrato %s %s' % (empleado.name, desde), 'employee_id': empleado.id, 'company_id': self.company.id, 'structure_type_id': self.tipo_quincenal.id,
            'wage': salario, 'date_start': desde, 'state': 'open'})
        contrato.generate_work_entries(date(2026, 9, 1), date(2026, 9, 30))
        return contrato

    def _confirmado(self, contrato, desde, hasta):
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo %s %s' % (contrato.employee_id.name, desde), 'employee_id': contrato.employee_id.id, 'contract_id': contrato.id,
            'company_id': self.company.id, 'struct_id': self.nomina.id, 'date_from': desde, 'date_to': hasta})
        recibo.compute_sheet()
        recibo.state = 'done'
        return recibo

    def _planilla_del_mes(self):
        """Dos empleados y tres recibos; devuelve el asistente validado."""
        dos = self._contrato('DosQuincenas', '1000000001')
        uno = self._contrato('UnaQuincena', '1000000002')
        self._confirmado(dos, date(2026, 9, 1), date(2026, 9, 15))
        self._confirmado(dos, date(2026, 9, 16), date(2026, 9, 30))
        self._confirmado(uno, date(2026, 9, 1), date(2026, 9, 15))
        asistente = self.env['l10n.co.hr.pila.wizard.v2'].create({'company_id': self.company.id, 'year': '2026', 'month': '09', 'tipo_planilla': 'E'})
        self.assertEqual(len(asistente._get_period_payslips(self.company, 2026, 9)), 3, 'Premisa: tres recibos confirmados de dos empleados')
        asistente.action_validate()
        self.assertTrue(asistente.validation_ok, asistente.validation_errors)
        return asistente

    def _archivo(self, asistente):
        asistente.action_generate_pila()
        lineas = base64.b64decode(asistente.file_data).decode('utf-8').splitlines()
        encabezado = [linea.split('|') for linea in lineas if linea.startswith('01|')]
        detalle = [linea.split('|') for linea in lineas if linea.startswith('02|')]
        self.assertEqual(len(encabezado), 1)
        return encabezado[0], detalle

    @staticmethod
    def _campo(definicion, linea, nombre):
        return linea[[campo for campo, _formato in definicion].index(nombre)]

    def test_el_encabezado_cuenta_cotizantes_y_no_recibos(self):
        encabezado, detalle = self._archivo(self._planilla_del_mes())
        self.assertEqual(len(detalle), 2)
        self.assertEqual(self._campo(pila_generator_v2._TIPO_01_FIELDS, encabezado, 'numero_total_cotizantes'), '2')

    def test_el_resumen_cuenta_cotizantes_y_no_repite_el_ibc_del_mes(self):
        asistente = self._planilla_del_mes()
        self.assertEqual(asistente.summary_total_employees, 2)
        self.assertAlmostEqual(asistente.summary_total_ibc, SALARIO * 1.5, delta=1.0)          # mes completo + una quincena
        self.assertAlmostEqual(asistente.summary_total_pension, SALARIO * 1.5 * 0.16, delta=100.0)

    def test_los_totales_del_resumen_son_los_del_archivo(self):
        asistente = self._planilla_del_mes()
        _encabezado, detalle = self._archivo(asistente)
        for total, campo in (('summary_total_ibc', 'ibc_pension'), ('summary_total_pension', 'cotizacion_pension'), ('summary_total_salud', 'cotizacion_salud')):
            en_el_archivo = sum(float(self._campo(pila_generator_v2._TIPO_02_FIELDS, linea, campo)) for linea in detalle)
            self.assertAlmostEqual(asistente[total], en_el_archivo, delta=2.0, msg=total)

    # ── el recibo del que salen los datos de la línea (H-F1-10) ──────
    def _con_aumento_en_la_segunda_quincena(self):
        """Otrosí: el contrato inicial termina el 15 y el nuevo, con 4.000.000, empieza el 16."""
        anterior = self._contrato('Aumento', '1000000003')
        anterior.write({'date_end': date(2026, 9, 15), 'state': 'close'})
        nuevo = self._contrato_de(anterior.employee_id, salario=4000000.0, desde=date(2026, 9, 16))
        return self._confirmado(anterior, date(2026, 9, 1), date(2026, 9, 15)) | self._confirmado(nuevo, date(2026, 9, 16), date(2026, 9, 30))

    def test_el_recibo_mas_reciente_no_depende_del_orden_en_que_llegan(self):
        recibos = self._con_aumento_en_la_segunda_quincena()
        segundo = recibos.filtered(lambda recibo: recibo.date_from == date(2026, 9, 16))
        asistente = self.env['l10n.co.hr.pila.wizard.v2']
        for entrada in (recibos, recibos.sorted('date_from'), recibos.sorted('date_from', reverse=True)):
            self.assertEqual(asistente._ne_recibo_mas_reciente(entrada), segundo)

    def test_la_linea_lleva_los_datos_del_recibo_mas_reciente(self):
        self._con_aumento_en_la_segunda_quincena()
        asistente = self.env['l10n.co.hr.pila.wizard.v2'].create({'company_id': self.company.id, 'year': '2026', 'month': '09', 'tipo_planilla': 'E'})
        asistente.action_validate()
        self.assertTrue(asistente.validation_ok, asistente.validation_errors)
        _encabezado, detalle = self._archivo(asistente)
        self.assertEqual(len(detalle), 1)
        self.assertEqual(self._campo(pila_generator_v2._TIPO_02_FIELDS, detalle[0], 'salario_basico'), '4000000')

    # ── las novedades salen de todos los recibos del mes ─────────────
    def _sin_calcular(self, contrato, desde, hasta, estructura=None):
        return self.env['hr.payslip'].create({
            'name': 'Recibo %s %s' % (contrato.employee_id.name, hasta), 'employee_id': contrato.employee_id.id, 'contract_id': contrato.id,
            'company_id': self.company.id, 'struct_id': (estructura or self.nomina).id, 'date_from': desde, 'date_to': hasta})

    def _quincenas(self, contrato):
        return self._sin_calcular(contrato, date(2026, 9, 1), date(2026, 9, 15)), self._sin_calcular(contrato, date(2026, 9, 16), date(2026, 9, 30))

    def _novedades(self, de_la_linea, recibos):
        return self.env['l10n.co.hr.pila.wizard.v2']._detect_novedades(de_la_linea, recibos)

    def test_una_ausencia_de_la_primera_quincena_se_marca_aunque_la_linea_salga_de_la_segunda(self):
        contrato = self._contrato('Incapacidad', '1000000004')
        ausencia = self.env['hr.leave'].create({
            'employee_id': contrato.employee_id.id, 'holiday_status_id': self.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_inc_comun').id,
            'request_date_from': date(2026, 9, 3), 'request_date_to': date(2026, 9, 4)})
        ausencia.action_validate()
        primera, segunda = self._quincenas(contrato)
        novedades = self._novedades(segunda, primera | segunda)
        self.assertEqual((novedades['ige'], novedades['fecha_inicio_ige'], novedades['fecha_fin_ige']), ('X', '2026-09-03', '2026-09-04'))

    def test_el_aporte_voluntario_de_cualquier_recibo_del_mes_se_marca(self):
        primera, segunda = self._quincenas(self._contrato('Voluntario', '1000000005'))
        regla = self.env['hr.salary.rule'].search([('struct_id', '=', self.nomina.id), ('code', '=', 'CO_PENSION_VOL')], limit=1)
        primera.write({'line_ids': [Command.create({
            'name': regla.name, 'code': regla.code, 'salary_rule_id': regla.id, 'contract_id': primera.contract_id.id, 'employee_id': primera.employee_id.id,
            'sequence': regla.sequence, 'amount': -100000.0, 'quantity': 1.0, 'rate': 100.0, 'total': -100000.0})]})
        self.assertEqual(self._novedades(segunda, primera | segunda)['avp'], 'X')

    def test_un_otrosi_dentro_del_mes_no_es_ingreso_ni_retiro(self):
        anterior = self._contrato('Otrosi', '1000000006')
        anterior.write({'date_end': date(2026, 9, 15), 'state': 'close'})
        nuevo = self._contrato_de(anterior.employee_id, desde=date(2026, 9, 16))
        primera = self._sin_calcular(anterior, date(2026, 9, 1), date(2026, 9, 15))
        segunda = self._sin_calcular(nuevo, date(2026, 9, 16), date(2026, 9, 30))
        novedades = self._novedades(segunda, primera | segunda)
        self.assertEqual((novedades['ing'], novedades['ret']), ('', ''))

    def test_el_retiro_con_liquidacion_marca_retiro_y_no_ingreso(self):
        """En la liquidación «Desde» es el inicio del contrato: el mes de la planilla sale del «Hasta»."""
        contrato = self._contrato('Retiro', '1000000007')
        contrato.write({'date_end': date(2026, 9, 20), 'state': 'close'})
        primera = self._sin_calcular(contrato, date(2026, 9, 1), date(2026, 9, 15))
        liquidacion = self._sin_calcular(contrato, date(2024, 1, 1), date(2026, 9, 20), self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion'))
        novedades = self._novedades(liquidacion, primera | liquidacion)
        self.assertEqual((novedades['ret'], novedades['fecha_ret'], novedades['ing']), ('X', '2026-09-20', ''))

    def test_el_ingreso_en_el_mes_se_marca_con_su_fecha(self):
        contrato = self._contrato('Ingreso', '1000000008', desde=date(2026, 9, 1))
        primera, segunda = self._quincenas(contrato)
        novedades = self._novedades(segunda, primera | segunda)
        self.assertEqual((novedades['ing'], novedades['fecha_ing'], novedades['ret']), ('X', '2026-09-01', ''))

    # ── campo 20 del encabezado: suma del IBC de Caja (.331) ─────────
    def test_el_valor_total_de_la_nomina_es_la_suma_del_ibc_de_caja_de_las_lineas(self):
        asistente = self._planilla_del_mes()
        encabezado, detalle = self._archivo(asistente)
        del_detalle = sum(int(self._campo(pila_generator_v2._TIPO_02_FIELDS, linea, 'ibc_ccf')) for linea in detalle)
        self.assertEqual(del_detalle, int(SALARIO * 1.5), 'Premisa: mes completo + una quincena, sin auxilio de transporte')
        self.assertEqual(self._campo(pila_generator_v2._TIPO_01_FIELDS, encabezado, 'valor_total_nomina'), str(del_detalle))
        self.assertAlmostEqual(asistente.summary_total_nomina, del_detalle, delta=0.01)

    def test_quien_no_aporta_a_caja_no_suma_en_el_valor_total(self):
        """Aprendiz en etapa lectiva (tipo 19): su registro lleva IBC de Caja en cero."""
        lectiva = self._contrato('Lectiva', '1000000010', tipo='19', tipo_contrato='4')
        empleado = self._contrato('Dependiente', '1000000011')
        for contrato in (lectiva, empleado):
            self._confirmado(contrato, date(2026, 9, 1), date(2026, 9, 15))
        asistente = self.env['l10n.co.hr.pila.wizard.v2'].create({'company_id': self.company.id, 'year': '2026', 'month': '09', 'tipo_planilla': 'E'})
        asistente.action_validate()
        self.assertTrue(asistente.validation_ok, asistente.validation_errors)
        encabezado, detalle = self._archivo(asistente)
        por_documento = {self._campo(pila_generator_v2._TIPO_02_FIELDS, linea, 'numero_documento'): self._campo(pila_generator_v2._TIPO_02_FIELDS, linea, 'ibc_ccf') for linea in detalle}
        self.assertEqual(por_documento, {'1000000010': '0', '1000000011': str(int(SALARIO / 2))})
        self.assertEqual(self._campo(pila_generator_v2._TIPO_01_FIELDS, encabezado, 'valor_total_nomina'), str(int(SALARIO / 2)))

    # ── marcas de ausencia por el código del tipo de entrada de trabajo (.331) ──
    def _marcas(self, documento, *ausencias):
        """Novedades de un empleado con las ausencias ``(tipo del módulo, desde, hasta)`` validadas en septiembre."""
        contrato = self._contrato('Marcas%s' % documento[-2:], documento)
        for tipo, desde, hasta in ausencias:
            self.env['hr.leave'].create({
                'employee_id': contrato.employee_id.id, 'holiday_status_id': self.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_%s' % tipo).id,
                'request_date_from': desde, 'request_date_to': hasta}).action_validate()
        primera, segunda = self._quincenas(contrato)
        return self._novedades(segunda, primera | segunda)

    def test_el_accidente_de_trabajo_es_irl_con_sus_dias_y_no_ige(self):
        novedades = self._marcas('1000000012', ('inc_laboral', date(2026, 9, 3), date(2026, 9, 4)), ('inc_laboral', date(2026, 9, 14), date(2026, 9, 16)))
        self.assertEqual(novedades['irl'], 5)
        self.assertEqual(novedades['ige'], '')
        self.assertEqual((novedades['fecha_inicio_irl'], novedades['fecha_fin_irl']), ('2026-09-14', '2026-09-16'))

    def test_los_dias_de_irl_se_cuentan_solo_dentro_del_mes(self):
        novedades = self._marcas('1000000013', ('inc_laboral', date(2026, 8, 28), date(2026, 9, 2)))
        self.assertEqual(novedades['irl'], 2)

    def test_sin_accidente_de_trabajo_el_campo_irl_es_cero(self):
        self.assertEqual(self._marcas('1000000014')['irl'], 0)

    def test_cada_ausencia_marca_su_campo(self):
        casos = (('inc_comun', 'ige', 'X'), ('lic_mat', 'lma', 'X'), ('lic_pat', 'lma', 'X'), ('vac', 'vac_lr', 'X'), ('lic_rem', 'vac_lr', 'L'), ('lic_nr', 'sln', 'X'))
        for indice, (tipo, campo, marca) in enumerate(casos):
            with self.subTest(tipo=tipo):
                novedades = self._marcas('10000001%02d' % (20 + indice), (tipo, date(2026, 9, 8), date(2026, 9, 9)))
                marcadas = {nombre: novedades[nombre] for nombre in ('sln', 'ige', 'lma', 'vac_lr', 'irl') if novedades[nombre]}
                self.assertEqual(marcadas, {campo: marca})

    def test_la_marca_no_depende_del_nombre_de_la_ausencia(self):
        tipo = self.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_lic_pat')
        tipo.sudo().name = 'Incapacidad con un nombre propio de la empresa'
        novedades = self._marcas('1000000015', ('lic_pat', date(2026, 9, 8), date(2026, 9, 9)))
        self.assertEqual((novedades['lma'], novedades['ige']), ('X', ''))

    def test_el_archivo_lleva_los_dias_de_irl_en_el_campo_numerico(self):
        """La incapacidad cae en la segunda quincena, que no se calcula aquí: el campo sale de las ausencias del mes."""
        contrato = self._contrato('ArchivoIrl', '1000000016')
        self.env['hr.leave'].create({
            'employee_id': contrato.employee_id.id, 'holiday_status_id': self.env.ref('l10n_co_nomina_electronica.hr_leave_type_co_inc_laboral').id,
            'request_date_from': date(2026, 9, 17), 'request_date_to': date(2026, 9, 18)}).action_validate()
        sin_ausencia = self._contrato('ArchivoSin', '1000000017')
        for recibo_de in (contrato, sin_ausencia):
            self._confirmado(recibo_de, date(2026, 9, 1), date(2026, 9, 15))
        asistente = self.env['l10n.co.hr.pila.wizard.v2'].create({'company_id': self.company.id, 'year': '2026', 'month': '09', 'tipo_planilla': 'E'})
        asistente.action_validate()
        self.assertTrue(asistente.validation_ok, asistente.validation_errors)
        _encabezado, detalle = self._archivo(asistente)
        irl = {self._campo(pila_generator_v2._TIPO_02_FIELDS, linea, 'numero_documento'): self._campo(pila_generator_v2._TIPO_02_FIELDS, linea, 'nov_irl') for linea in detalle}
        self.assertEqual(irl, {'1000000016': '2', '1000000017': '0'})

    # ── un reembolso resta (.331) ────────────────────────────────────
    def _con_aporte_voluntario(self, contrato):
        if not contrato.l10n_co_ne_pension_voluntaria_partner_id:          # la deducción calculada exige el contacto del fondo
            contrato.l10n_co_ne_pension_voluntaria_partner_id = self.env['res.partner'].create({'name': 'Fondo Voluntario Cotizantes', 'l10n_co_entity_type': 'other'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo %s con aporte' % contrato.employee_id.name, 'employee_id': contrato.employee_id.id, 'contract_id': contrato.id, 'company_id': self.company.id,
            'struct_id': self.nomina.id, 'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15),
            'input_line_ids': [Command.create({'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_pension_vol').id, 'code': 'CO_PENSION_VOL', 'amount': 200000.0})]})
        recibo.compute_sheet()
        recibo.state = 'done'
        return recibo

    def test_tras_reembolsar_y_rehacer_la_pila_lleva_el_fsp_y_el_aporte_voluntario_una_sola_vez(self):
        """16.000.000 al mes: la quincena (8.000.000) pasa de 4 SMMLV y descuenta FSP 1 % = 80.000. Original + reembolso + recibo rehecho: queda uno."""
        contrato = self._contrato('Reembolso', '1000000018')
        contrato.wage = 16000000.0
        original = self._con_aporte_voluntario(contrato)
        original.refund_sheet()
        reembolso = self.env['hr.payslip'].search([('contract_id', '=', contrato.id), ('credit_note', '=', True)])
        self.assertEqual(len(reembolso), 1)
        reembolso.state = 'done'
        rehecho = self._con_aporte_voluntario(contrato)
        self.assertEqual([sum(r.line_ids.filtered(lambda l: l.code == 'CO_FSP').mapped('total')) for r in (original, reembolso, rehecho)], [-80000.0, 80000.0, -80000.0], 'Premisa')
        asistente = self.env['l10n.co.hr.pila.wizard.v2'].create({'company_id': self.company.id, 'year': '2026', 'month': '09', 'tipo_planilla': 'E'})
        asistente.action_validate()
        self.assertTrue(asistente.validation_ok, asistente.validation_errors)
        _encabezado, detalle = self._archivo(asistente)
        self.assertEqual(len(detalle), 1)
        valores = {campo: self._campo(pila_generator_v2._TIPO_02_FIELDS, detalle[0], campo) for campo in ('aporte_fsp_subcuenta', 'avp_afiliado', 'total_cotizacion_pension', 'nov_avp')}
        self.assertEqual(valores, {'aporte_fsp_subcuenta': '80000', 'avp_afiliado': '200000', 'total_cotizacion_pension': '1560000', 'nov_avp': 'X'})

    def test_un_aporte_voluntario_reembolsado_no_se_marca(self):
        primera, segunda = self._quincenas(self._contrato('Devuelto', '1000000019'))
        regla = self.env['hr.salary.rule'].search([('struct_id', '=', self.nomina.id), ('code', '=', 'CO_PENSION_VOL')], limit=1)
        for recibo, valor in ((primera, -100000.0), (segunda, 100000.0)):
            recibo.write({'line_ids': [Command.create({
                'name': regla.name, 'code': regla.code, 'salary_rule_id': regla.id, 'contract_id': recibo.contract_id.id, 'employee_id': recibo.employee_id.id,
                'sequence': regla.sequence, 'amount': valor, 'quantity': 1.0, 'rate': 100.0, 'total': valor})]})
        self.assertEqual(self._novedades(segunda, primera | segunda)['avp'], '')
