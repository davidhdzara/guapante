# -*- coding: utf-8 -*-
"""Fase 1 del doc 68 (.280): «Días trabajados» del recibo desde los días PAGADOS, no desde las horas de las entradas de trabajo.

Defecto (QA, prenomina de abril de 2026 de Guapante, quincenal, 60c #21/#23/#24): la pestaña mostraba «Festivo 2,05 + Descanso 2,05 +
Asistencia 10,98 = 15,07 días» (el nativo reparte las horas de TODAS las entradas por tipo) mientras el recibo pagaba 15. Ahora la línea
«Asistencia» (WORK100) es UNA sola, con los días que paga CO_BASICO (``_ne_dias_pagables``), y el festivo y el descanso (parámetro
``l10n_co_dias_trabajados_ocultar``) no aparecen. Vacaciones, licencias e incapacidades conservan su línea; «OUT» (ingreso o retiro a mitad
del periodo) la agrega el nativo.

Invariantes que se prueban: pago (CO_BASICO, ``_ne_dias_pagables``, de donde sale el DiasTrabajados del XML) IGUAL antes y después; la
suma de los importes de las líneas (= ``BASIC``, que alimenta ``GROSS`` y la base de retención) IGUAL antes y después EN TODOS LOS CASOS,
también con «OUT». ``amount`` = salario × horas de la línea / horas totales (hr_payslip_worked_days.py:36-47 del servidor, leído por Tech
Lead) y las horas de OUT entran al denominador; por eso «Asistencia» conserva las HORAS originales (las del nativo más las de los tipos
ocultos) y solo cambia lo que se muestra: los días y el nombre (explícito, sin « (Half-Day)»). Decisión de Tech Lead, 17-nov-2026: no se
cambia plata. Las cifras antes/después quedan en el log con el prefijo ``[.280]``.

«Antes» = el comportamiento nativo: se obtiene con ``_ne_aplica_dias_por_asistencia`` en False y el botón nativo «Actualizar desde
entradas de trabajo». Valores a mano: septiembre de 2026 empieza en martes (22 días lunes a viernes, 30 comerciales); calendario de la
compañía de prueba = 40 h/semana, 8 h por día. NO EJECUTADAS en Odoo.
"""

import logging
from datetime import date
from unittest.mock import patch

from lxml import etree

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestDiasPorAsistencia(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Días por Asistencia'})
        # El entorno y los datos comparten compañía: la conversión nativa de hr.leave a hr.work.entry filtra por la compañía del contrato.
        cls.env = cls.company.with_company(cls.company).env
        ref = cls.env.ref
        cls.tipo = ref('l10n_co_nomina_electronica.hr_payroll_structure_type_co')
        cls.tipo_semanal = cls.env['hr.payroll.structure.type'].create({
            'name': 'Tipo Días Asistencia Semanal', 'country_id': ref('base.co').id, 'default_schedule_pay': 'weekly'})
        cls.general = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.liquidacion = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.prima = ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')
        cls.leave_vac = ref('l10n_co_nomina_electronica.hr_leave_type_co_vac')
        cls.leave_lic_nr = ref('l10n_co_nomina_electronica.hr_leave_type_co_lic_nr')
        cls.tipo_vac = ref('l10n_co_nomina_electronica.hr_work_entry_type_co_vac')
        cls.tipo_lic_nr = ref('l10n_co_nomina_electronica.hr_work_entry_type_co_lic_nr')
        cls.leave_inc_comun = ref('l10n_co_nomina_electronica.hr_leave_type_co_inc_comun')
        cls.leave_inc_laboral = ref('l10n_co_nomina_electronica.hr_leave_type_co_inc_laboral')
        cls.leave_lic_mat = ref('l10n_co_nomina_electronica.hr_leave_type_co_lic_mat')
        cls.tipo_inc_comun = ref('l10n_co_nomina_electronica.hr_work_entry_type_co_inc_comun')
        cls.n = 0

    # ── fixtures ─────────────────────────────────────────────────────
    def _tipo_entrada(self, codigo, nombre, is_leave):
        """El tipo de entrada de trabajo con ese código si la base ya lo trae (el código es único); si no, lo crea."""
        return self.env['hr.work.entry.type'].search([('code', '=', codigo)], limit=1) or self.env['hr.work.entry.type'].create({
            'name': nombre, 'code': codigo, 'is_leave': is_leave})

    def _contrato(self, ingreso=date(2024, 1, 1), fin=None, wage=3000000.0, tipo=None):
        type(self).n += 1
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado Días Asistencia %s' % self.n, 'company_id': self.company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        vals = {
            'name': 'Contrato Días Asistencia %s' % self.n, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': (tipo or self.tipo).id, 'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00', 'wage': wage, 'date_start': ingreso, 'state': 'open'}
        if fin:
            vals['date_end'] = fin
        return empleado, self.env['hr.contract'].create(vals)

    def _recibo(self, desde=date(2026, 9, 1), hasta=date(2026, 9, 30), estructura=None, calcular=True, **kwargs):
        empleado, contrato = self._contrato(**kwargs)
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Días Asistencia %s' % desde, 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': self.company.id, 'struct_id': (estructura or self.general).id, 'date_from': desde, 'date_to': hasta})
        if calcular:
            recibo.compute_sheet()
        return recibo

    def _ausencia(self, recibo, tipo_ausencia, desde, hasta):
        """Ausencia validada del empleado del recibo, con las entradas de trabajo del contrato generadas antes (como el cron diario)."""
        recibo.contract_id.generate_work_entries(desde, hasta)
        ausencia = self.env['hr.leave'].create({
            'employee_id': recibo.employee_id.id, 'holiday_status_id': tipo_ausencia.id,
            'request_date_from': desde, 'request_date_to': hasta})
        ausencia.action_validate()
        self.assertEqual(ausencia.state, 'validate')

    def _recibo_con_ausencia(self, tipo_ausencia, desde, hasta, **kwargs):
        """Recibo de septiembre con una ausencia ya validada: las líneas de días se generan al refrescar desde las entradas de trabajo."""
        recibo = self._recibo(calcular=False, **kwargs)
        self._ausencia(recibo, tipo_ausencia, desde, hasta)
        recibo.action_refresh_from_work_entries()
        return recibo

    def _como_antes(self, recibo):
        """Regenera días y hoja con el comportamiento NATIVO (sin la línea de días pagados)."""
        with patch.object(type(recibo), '_ne_aplica_dias_por_asistencia', return_value=False):
            recibo.action_refresh_from_work_entries()

    def _como_ahora(self, recibo):
        recibo.action_refresh_from_work_entries()

    def _linea(self, recibo, codigo):
        return recibo.line_ids.filtered(lambda l: l.code == codigo)

    def _dias(self, recibo, codigo):
        return sum(recibo.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.code == codigo).mapped('number_of_days'))

    def _horas(self, recibo, codigo):
        return sum(recibo.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.code == codigo).mapped('number_of_hours'))

    def _cifras(self, recibo):
        """Lo que importa de un recibo calculado: pago, días pagables, suma de importes de las líneas y las líneas BASIC/GROSS."""
        return {
            'co_basico': self._linea(recibo, 'CO_BASICO').total, 'cantidad': self._linea(recibo, 'CO_BASICO').quantity,
            'pagables': recibo._ne_dias_pagables(), 'suma': sum(recibo.worked_days_line_ids.mapped('amount')),
            'basic': self._linea(recibo, 'BASIC').total, 'gross': self._linea(recibo, 'GROSS').total}

    def _pago(self, recibo, codigos):
        """Total y cantidad de las líneas de pago ``codigos`` más el neto: lo que NO debe cambiar al mostrar otros días en la pestaña."""
        cifras = {'neto': self._linea(recibo, 'CO_NETO').total}
        for codigo in codigos:
            cifras['%s_total' % codigo] = self._linea(recibo, codigo).total
            cifras['%s_cantidad' % codigo] = self._linea(recibo, codigo).quantity
        return cifras

    def _assert_pago_igual_antes_y_despues(self, recibo, codigos):
        """Regenera el recibo como lo calculaba el nativo y compara pago, días pagables, suma de importes, BASIC y GROSS con los de ahora."""
        despues = dict(self._cifras(recibo), **self._pago(recibo, codigos))
        self._como_antes(recibo)
        antes = dict(self._cifras(recibo), **self._pago(recibo, codigos))
        self.assertEqual(sorted(antes), sorted(despues))
        for clave in despues:
            self.assertAlmostEqual(despues[clave], antes[clave], delta=0.05, msg=clave)
        return antes, despues

    def _valores(self, recibo, *lineas):
        """Lista de valores de líneas de días como la entrega el nativo: (tipo, días, horas) -> diccionario."""
        return [{'sequence': tipo.sequence, 'work_entry_type_id': tipo.id, 'number_of_days': dias, 'number_of_hours': horas}
                for tipo, dias, horas in lineas]

    # ── parámetro ────────────────────────────────────────────────────
    def test_el_parametro_oculta_festivo_y_descanso(self):
        recibo = self._recibo(calcular=False)
        self.assertEqual(recibo._ne_codigos_dias_ocultos(), {'FEST', 'DESCANSO'})

    # ── periodos completos: Asistencia = días pagados ─────────────────
    def test_mes_completo_asistencia_son_los_30_dias_pagados(self):
        recibo = self._recibo()
        asistencia = recibo.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.code == 'WORK100')
        self.assertEqual(len(asistencia), 1)
        self.assertEqual(asistencia.number_of_days, 30.0)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 30.0)
        self.assertEqual(recibo._ne_dias_pagables(), 30.0)
        self.assertEqual(len(recibo.worked_days_line_ids), 1, 'Sin ausencias ni OUT, solo la línea de Asistencia')
        self.assertEqual(asistencia.name, recibo._ne_tipo_asistencia().name, 'Nombre explícito, sin « (Half-Day)»')
        horas_ahora = asistencia.number_of_hours
        self._como_antes(recibo)
        self.assertAlmostEqual(horas_ahora, self._horas(recibo, 'WORK100'), places=4, msg='Las horas de Asistencia son las del nativo')

    def test_quincena_asistencia_son_15_dias_pagados(self):
        """Las dos quincenas de septiembre (1 al 15 y 16 al 30): 15 días cada una, igual a la cantidad de CO_BASICO."""
        empleado, contrato = self._contrato()
        for desde, hasta in ((date(2026, 9, 1), date(2026, 9, 15)), (date(2026, 9, 16), date(2026, 9, 30))):
            recibo = self.env['hr.payslip'].create({
                'name': 'Quincena %s' % desde, 'employee_id': empleado.id, 'contract_id': contrato.id,
                'company_id': self.company.id, 'struct_id': self.general.id, 'date_from': desde, 'date_to': hasta})
            recibo.compute_sheet()
            self.assertEqual(self._dias(recibo, 'WORK100'), 15.0, desde)
            self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 15.0, desde)
            self.assertEqual(recibo._ne_dias_pagables(), 15.0, desde)

    def test_semana_asistencia_son_7_dias_pagados(self):
        """Pago semanal: 7 días calendario (sábado 2 a viernes 8 de mayo de 2026)."""
        recibo = self._recibo(date(2026, 5, 2), date(2026, 5, 8), tipo=self.tipo_semanal)
        self.assertEqual(self._dias(recibo, 'WORK100'), 7.0)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 7.0)

    # ── festivo y descanso no trabajados ─────────────────────────────
    def test_festivo_y_descanso_no_trabajados_no_aparecen_y_asistencia_es_15(self):
        """El caso de QA de abril (1 al 15, gerente): el nativo daba Asistencia 10,98 + Festivo 2,05 + Descanso 2,05 = 15,07. Ahora solo
        «Asistencia» con 15, la primera y única."""
        asistencia = self._recibo(calcular=False)._ne_tipo_asistencia()
        festivo = self._tipo_entrada('FEST', 'Festivo', True)
        descanso = self._tipo_entrada('DESCANSO', 'Descanso', False)
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15), calcular=False)
        valores = self._valores(
            recibo, (asistencia, 10.98, 80.5), (festivo, 2.05, 15.0), (descanso, 2.05, 15.0))
        resultado = recibo._ne_ajustar_dias_por_asistencia(valores)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]['work_entry_type_id'], asistencia.id)
        self.assertEqual(resultado[0]['number_of_days'], 15.0)
        self.assertAlmostEqual(resultado[0]['number_of_hours'], 80.5 + 15.0 + 15.0, places=4)
        self.assertEqual(resultado[0]['name'], asistencia.name)

    def test_la_asistencia_no_depende_de_las_horas_de_las_entradas(self):
        """Una entrada de más o de menos (el empleado sin entrada del 1.º de abril, 9,96 días) no cambia los días pagados."""
        asistencia = self._recibo(calcular=False)._ne_tipo_asistencia()
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15), calcular=False)
        for dias, horas in ((9.96, 73.0), (10.98, 80.5), (14.0, 103.0)):
            resultado = recibo._ne_ajustar_dias_por_asistencia(self._valores(recibo, (asistencia, dias, horas)))
            self.assertEqual(resultado[0]['number_of_days'], 15.0, dias)
            self.assertAlmostEqual(resultado[0]['number_of_hours'], horas, places=4, msg='Las horas son las del nativo')

    # ── ausencias ────────────────────────────────────────────────────
    def test_la_ausencia_conserva_su_linea_y_asistencia_descuenta_sus_dias(self):
        """Mes de 30 días con 5 días hábiles de vacaciones: Asistencia = 25, la línea de vacaciones intacta y en segundo lugar."""
        asistencia = self._recibo(calcular=False)._ne_tipo_asistencia()
        recibo = self._recibo(calcular=False)
        valores = self._valores(recibo, (asistencia, 17.0, 136.0), (self.tipo_vac, 5.0, 40.0))
        resultado = recibo._ne_ajustar_dias_por_asistencia(valores)
        self.assertEqual([r['work_entry_type_id'] for r in resultado], [asistencia.id, self.tipo_vac.id])
        self.assertEqual(resultado[0]['number_of_days'], 25.0)
        self.assertAlmostEqual(resultado[0]['number_of_hours'], 136.0, places=4)
        self.assertEqual(resultado[1], valores[1], 'La línea de vacaciones no se toca')
        self.assertEqual(recibo._ne_dias_pagables(valores=valores), 25.0)

    def test_sin_dias_pagados_no_hay_linea_de_asistencia(self):
        """Todo el mes en vacaciones: no queda ningún día pagable por el básico, la línea de Asistencia no se crea."""
        asistencia = self._recibo(calcular=False)._ne_tipo_asistencia()
        recibo = self._recibo(calcular=False)
        valores = self._valores(recibo, (asistencia, 0.0, 0.0), (self.tipo_vac, 30.0, 240.0))
        resultado = recibo._ne_ajustar_dias_por_asistencia(valores)
        self.assertEqual([r['work_entry_type_id'] for r in resultado], [self.tipo_vac.id])
        # Con horas de un tipo oculto (festivo dentro de las ausencias) la línea se conserva con 0 días: el total de horas no cambia.
        festivo = self._tipo_entrada('FEST', 'Festivo', True)
        valores = self._valores(recibo, (festivo, 1.0, 8.0), (self.tipo_vac, 30.0, 240.0))
        resultado = recibo._ne_ajustar_dias_por_asistencia(valores)
        self.assertEqual([r['work_entry_type_id'] for r in resultado], [asistencia.id, self.tipo_vac.id])
        self.assertEqual((resultado[0]['number_of_days'], resultado[0]['number_of_hours']), (0.0, 8.0))

    def test_vacaciones_reales_asistencia_es_lo_que_paga_co_basico(self):
        """Con una ausencia validada de verdad: Asistencia = CO_BASICO.quantity = ``_ne_dias_pagables()`` (leído de las líneas
        guardadas) = 30 - días de la línea de vacaciones; pago y suma de importes iguales a los del nativo."""
        recibo = self._recibo_con_ausencia(self.leave_vac, date(2026, 9, 16), date(2026, 9, 30))
        recibo.compute_sheet()
        dias_vac = self._dias(recibo, 'CO_VAC')
        self.assertGreaterEqual(dias_vac, 1, 'La ausencia validada no generó línea CO_VAC')
        despues = self._cifras(recibo)
        self.assertEqual(self._dias(recibo, 'WORK100'), 30.0 - dias_vac)
        self.assertEqual(despues['cantidad'], 30.0 - dias_vac)
        self.assertEqual(despues['pagables'], 30.0 - dias_vac)
        self._como_antes(recibo)
        antes = self._cifras(recibo)
        self.assertEqual(self._dias(recibo, 'CO_VAC'), dias_vac, 'El nativo y el módulo cuentan los mismos días de vacaciones')
        self.assertNotEqual(self._dias(recibo, 'WORK100'), 30.0 - dias_vac, 'Premisa: el nativo mostraba otra cosa en Asistencia')
        for clave in ('co_basico', 'cantidad', 'pagables'):
            self.assertAlmostEqual(despues[clave], antes[clave], places=2, msg=clave)
        for clave in ('suma', 'basic', 'gross'):
            self.assertAlmostEqual(despues[clave], antes[clave], delta=0.05, msg=clave)

    def test_licencia_sin_sueldo_antes_y_despues(self):
        """Licencia no remunerada del 1 al 5: se descuenta del básico. CO_BASICO, días pagables, BASIC y GROSS iguales antes y después
        (la estructura general no declara tipos de entrada no pagados: todas las líneas son pagadas y la suma es el salario)."""
        recibo = self._recibo_con_ausencia(self.leave_lic_nr, date(2026, 9, 1), date(2026, 9, 5))
        recibo.compute_sheet()
        dias = self._dias(recibo, 'CO_LIC_NR')
        self.assertGreaterEqual(dias, 1, 'La ausencia validada no generó línea CO_LIC_NR')
        self.assertFalse(recibo.struct_id.unpaid_work_entry_type_ids, 'Premisa: sin tipos de entrada no pagados en la estructura')
        despues = self._cifras(recibo)
        self.assertEqual(self._dias(recibo, 'WORK100'), 30.0 - dias)
        self._como_antes(recibo)
        antes = self._cifras(recibo)
        _logger.info('[.280] licencia sin sueldo (%s d) antes=%s despues=%s', dias, antes, despues)
        self.assertLess(despues['co_basico'], recibo.contract_id.wage)
        for clave in ('co_basico', 'cantidad', 'pagables'):
            self.assertAlmostEqual(despues[clave], antes[clave], places=2, msg=clave)
        for clave in ('suma', 'basic', 'gross'):
            self.assertAlmostEqual(despues[clave], antes[clave], delta=0.05, msg=clave)

    # ── mes completo y quincena: la suma no cambia ────────────────────
    def test_mes_y_quincena_completos_la_suma_de_importes_no_cambia(self):
        """Invariante de retención: sin ausencias ni OUT, BASIC (suma de los importes de las líneas) y GROSS son iguales antes y después
        (el salario completo), y CO_BASICO también."""
        for desde, hasta in ((date(2026, 9, 1), date(2026, 9, 30)), (date(2026, 9, 1), date(2026, 9, 15))):
            recibo = self._recibo(desde, hasta)
            despues = self._cifras(recibo)
            self._como_antes(recibo)
            antes = self._cifras(recibo)
            _logger.info('[.280] %s a %s antes=%s despues=%s', desde, hasta, antes, despues)
            self.assertAlmostEqual(despues['suma'], recibo.contract_id.wage, delta=0.05, msg='la suma es el salario mensual completo')
            for clave in ('co_basico', 'cantidad', 'pagables', 'suma', 'basic', 'gross'):
                self.assertAlmostEqual(despues[clave], antes[clave], delta=0.05, msg='%s %s' % (desde, clave))

    # ── ingreso y retiro a mitad del periodo (línea OUT) ──────────────
    def test_ingreso_a_mitad_de_mes_ni_el_pago_ni_la_suma_de_importes_cambian(self):
        """Contrato desde el 16-sep, mes de septiembre: 15 días pagados. Con OUT las horas de OUT entran al denominador de ``amount``; por
        eso «Asistencia» conserva las horas del nativo (88 h) y la suma de importes NO cambia. A mano (salario 3.000.000, 8 h/día): OUT =
        11 días hábiles x 8 h = 88 h; Asistencia 88 h; suma = 3.000.000 x 88/176 = 1.500.000 antes y después (Tech Lead, 17-nov-2026:
        no se cambia plata; con 120 h daría 1.730.769,23). CO_BASICO = 1.500.000. Nombre sin « (Half-Day)» aunque 88 h / 15 días < 8 h."""
        recibo = self._recibo(ingreso=date(2026, 9, 16))
        despues = self._cifras(recibo)
        horas_out = self._horas(recibo, 'OUT')
        self.assertGreater(horas_out, 0, 'Premisa: el nativo agrega la línea OUT (contrato desde el 16)')
        asistencia = recibo.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.code == 'WORK100')
        self.assertEqual(asistencia.number_of_days, 15.0)
        self.assertEqual(asistencia.name, recibo._ne_tipo_asistencia().name, 'Nombre explícito, sin « (Half-Day)»')
        wage = recibo.contract_id.wage
        horas_asistencia = asistencia.number_of_hours
        self.assertAlmostEqual(despues['suma'], wage * horas_asistencia / (horas_asistencia + horas_out), delta=0.05)
        self.assertAlmostEqual(despues['basic'], despues['suma'], delta=0.05)
        self._como_antes(recibo)
        antes = self._cifras(recibo)
        horas_antes = self._horas(recibo, 'WORK100')
        self.assertAlmostEqual(horas_asistencia, horas_antes, places=4, msg='Asistencia conserva las horas del nativo')
        self.assertAlmostEqual(antes['suma'], wage * horas_antes / (horas_antes + self._horas(recibo, 'OUT')), delta=0.05)
        _logger.info('[.280] ingreso 16-sep, OUT=%s h, Asistencia=%s h: ANTES suma/BASIC=%s GROSS=%s | DESPUES suma/BASIC=%s GROSS=%s | '
                     'CO_BASICO antes=%s despues=%s', horas_out, horas_antes, antes['suma'], antes['gross'], despues['suma'],
                     despues['gross'], antes['co_basico'], despues['co_basico'])
        for clave in ('co_basico', 'cantidad', 'pagables'):
            self.assertAlmostEqual(despues[clave], antes[clave], places=2, msg=clave)
        for clave in ('suma', 'basic', 'gross'):
            self.assertAlmostEqual(despues[clave], antes[clave], delta=0.05, msg=clave)
        self.assertAlmostEqual(despues['co_basico'], wage * 15 / 30, places=2)

    def test_retiro_a_mitad_de_mes_asistencia_son_los_dias_bajo_contrato(self):
        """Contrato hasta el 10-sep: 10 días pagados, línea OUT del nativo (11 al 30) intacta, CO_BASICO por 10 días."""
        recibo = self._recibo(fin=date(2026, 9, 10))
        despues = self._cifras(recibo)
        self.assertGreater(self._horas(recibo, 'OUT'), 0, 'Premisa: el nativo agrega la línea OUT (contrato hasta el 10)')
        self.assertEqual(self._dias(recibo, 'WORK100'), 10.0)
        self.assertEqual(despues['cantidad'], 10.0)
        self._como_antes(recibo)
        antes = self._cifras(recibo)
        _logger.info('[.280] retiro 10-sep: antes=%s despues=%s', antes, despues)
        for clave in ('co_basico', 'cantidad', 'pagables'):
            self.assertAlmostEqual(despues[clave], antes[clave], places=2, msg=clave)
        for clave in ('suma', 'basic', 'gross'):
            self.assertAlmostEqual(despues[clave], antes[clave], delta=0.05, msg=clave)

    # ── recibos ya calculados y estructuras que no se tocan ───────────
    def test_un_recibo_ya_calculado_no_cambia_solo_y_el_boton_lo_actualiza(self):
        """Un recibo calculado con el comportamiento anterior conserva sus líneas al «Calcular hoja» (el nativo no regenera los días);
        el botón «Actualizar desde entradas de trabajo» (borrador) las rearma con los días pagados."""
        recibo = self._recibo()
        self._como_antes(recibo)
        dias_nativos = self._dias(recibo, 'WORK100')
        self.assertNotEqual(dias_nativos, 30.0, 'Premisa: en septiembre el nativo cuenta los días lunes a viernes, no 30')
        recibo.compute_sheet()
        self.assertEqual(self._dias(recibo, 'WORK100'), dias_nativos)
        self._como_ahora(recibo)
        self.assertEqual(self._dias(recibo, 'WORK100'), 30.0)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 30.0)

    def test_solo_la_estructura_general_de_una_compania_colombiana_usa_los_dias_pagados(self):
        general = self._recibo(calcular=False)
        liquidacion = self._recibo(estructura=self.liquidacion, calcular=False)
        prima = self._recibo(estructura=self.prima, calcular=False)
        self.assertTrue(general._ne_aplica_dias_por_asistencia())
        self.assertFalse(liquidacion._ne_aplica_dias_por_asistencia())
        self.assertFalse(prima._ne_aplica_dias_por_asistencia())

    # ── .281: días calendario en las 4 líneas de ausencia ─────────────
    def test_incapacidad_muestra_los_dias_calendario_que_se_pagan(self):
        """Incapacidad común del viernes 11 al lunes 14 de septiembre: 4 días calendario (viernes, sábado, domingo y lunes), pero el calendario
        de la compañía (lun-vie, 8 h) solo tiene entradas el viernes y el lunes: el nativo mostraba 2 días (16 h / 8). Ahora la línea muestra
        4, Asistencia = 30 - 4 = 26 y la pestaña suma los 30 días del mes. Nombre sin « (Half-Day)» (16 h / 4 días < 8 h)."""
        recibo = self._recibo_con_ausencia(self.leave_inc_comun, date(2026, 9, 11), date(2026, 9, 14))
        linea = recibo.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.code == 'CO_INC_COMUN')
        self.assertEqual(len(linea), 1)
        self.assertEqual(linea.number_of_days, 4.0)
        self.assertEqual(linea.number_of_days, recibo._ne_ausencia_calendario('CO_INC_COMUN')[0])
        self.assertEqual(linea.name, self.tipo_inc_comun.name, 'Nombre explícito, sin « (Half-Day)»')
        self.assertEqual(self._dias(recibo, 'WORK100'), 26.0)
        self.assertEqual(sum(recibo.worked_days_line_ids.mapped('number_of_days')), 30.0)
        horas_ahora = linea.number_of_hours
        self._como_antes(recibo)
        dias_nativos = self._dias(recibo, 'CO_INC_COMUN')
        self.assertLess(dias_nativos, 4.0, 'Premisa: el nativo mostraba horas / horas por día, no los días calendario')
        self.assertAlmostEqual(self._horas(recibo, 'CO_INC_COMUN'), horas_ahora, places=4, msg='Las horas de la línea no se tocan')

    def test_el_pago_de_la_incapacidad_no_cambia_antes_y_despues(self):
        """Solo presentación: CO_BASICO, CO_AUX_TRANS, CO_INC_COMUN, el neto, los días pagables y la suma de importes (BASIC, GROSS) iguales."""
        recibo = self._recibo_con_ausencia(self.leave_inc_comun, date(2026, 9, 11), date(2026, 9, 14))
        recibo.compute_sheet()
        antes, despues = self._assert_pago_igual_antes_y_despues(recibo, ('CO_BASICO', 'CO_AUX_TRANS', 'CO_INC_COMUN'))
        _logger.info('[.281] incapacidad 11-14 sep: antes=%s despues=%s', antes, despues)
        self.assertGreater(despues['CO_INC_COMUN_total'], 0, 'Premisa: la incapacidad se pagó')

    def test_accidente_de_trabajo_muestra_los_dias_calendario(self):
        recibo = self._recibo_con_ausencia(self.leave_inc_laboral, date(2026, 9, 11), date(2026, 9, 14))
        self.assertEqual(self._dias(recibo, 'CO_INC_LABORAL'), 4.0)
        self.assertEqual(self._dias(recibo, 'WORK100'), 26.0)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 26.0)

    def test_maternidad_que_cruza_el_periodo_muestra_solo_los_dias_del_periodo_y_el_pago_no_cambia(self):
        """Licencia de maternidad del 25-ago al 9-sep: en el recibo de septiembre cuenta el tramo 1 al 9 = 9 días calendario (el nativo mostraba
        los 7 días hábiles con entrada: 1, 2, 3, 4, 7, 8 y 9). Asistencia = 30 - 9 = 21; el pago, igual."""
        recibo = self._recibo_con_ausencia(self.leave_lic_mat, date(2026, 8, 25), date(2026, 9, 9))
        recibo.compute_sheet()
        self.assertEqual(self._dias(recibo, 'CO_LIC_MAT'), 9.0)
        self.assertEqual(self._dias(recibo, 'WORK100'), 21.0)
        self._assert_pago_igual_antes_y_despues(recibo, ('CO_BASICO', 'CO_LIC_MAT'))

    def test_sin_ausencia_validada_la_linea_nativa_queda_igual(self):
        """Entradas de trabajo de incapacidad sin hr.leave validada (no hay fechas que contar): la línea no se reemplaza."""
        asistencia = self._recibo(calcular=False)._ne_tipo_asistencia()
        recibo = self._recibo(calcular=False)
        valores = self._valores(recibo, (asistencia, 22.0, 176.0), (self.tipo_inc_comun, 2.0, 16.0))
        resultado = recibo._ne_ajustar_dias_por_asistencia(valores)
        self.assertEqual(resultado[1], valores[1])

    def test_un_tipo_marcado_sin_sueldo_no_se_reemplaza(self):
        """Guarda: el código de un tipo ``unpaid`` SÍ lo lee ``_ne_dias_habiles_excluidos`` de la línea; reemplazar sus días movería el pago.
        Sin la marca, la línea muestra los 4 días calendario; con la marca queda igual que la entrega el nativo."""
        recibo = self._recibo_con_ausencia(self.leave_inc_comun, date(2026, 9, 11), date(2026, 9, 14))
        asistencia = recibo._ne_tipo_asistencia()
        valores = self._valores(recibo, (asistencia, 22.0, 176.0), (self.tipo_inc_comun, 2.0, 16.0))
        self.assertEqual(recibo._ne_ajustar_dias_por_asistencia(valores)[1]['number_of_days'], 4.0)
        self.leave_inc_comun.unpaid = True
        self.assertIn('CO_INC_COMUN', recibo._ne_codigos_tipos_no_remunerados())
        self.assertEqual(recibo._ne_ajustar_dias_por_asistencia(valores)[1], valores[1])

    def test_los_tipos_de_ausencia_de_dias_calendario_no_son_sin_sueldo_de_fabrica(self):
        """Premisa de la guarda: solo la licencia no remunerada trae ``unpaid`` (data/l10n_co_ausencias_data.xml)."""
        recibo = self._recibo(calcular=False)
        no_remunerados = recibo._ne_codigos_tipos_no_remunerados()
        self.assertIn('CO_LIC_NR', no_remunerados)
        for codigo in ('CO_INC_COMUN', 'CO_INC_LABORAL', 'CO_LIC_MAT', 'CO_LIC_PAT'):
            self.assertNotIn(codigo, no_remunerados, codigo)

    # ── .281: vista de la pestaña ─────────────────────────────────────
    def _pagina_de_dias(self):
        arch = self.env['hr.payslip'].get_view(view_type='form')['arch']
        paginas = etree.fromstring(arch).xpath("//page[@name='worked_days_input']")
        self.assertEqual(len(paginas), 1, 'Falta la página «Días trabajados y entradas» del formulario del recibo')
        return paginas[0]

    def test_la_vista_cambia_la_etiqueta_de_las_entradas_por_novedades_de_nomina(self):
        pagina = self._pagina_de_dias()
        # Se verifica el RESULTADO (no el selector de la herencia): los separadores directos de la página, en orden.
        separadores = pagina.xpath('./separator')
        etiquetas = [separador.get('string') for separador in separadores]
        self.assertEqual(etiquetas.count('Novedades de nómina'), 1, etiquetas)
        nuevo = separadores[etiquetas.index('Novedades de nómina')]
        self.assertTrue(nuevo.xpath("following-sibling::field[@name='input_line_ids']"), 'Va antes de la lista de entradas')
        self.assertTrue(nuevo.xpath("preceding-sibling::field[@name='worked_days_line_ids']"), 'Va después de la lista de días')
        self.assertEqual(len(nuevo.xpath('preceding-sibling::separator')), len(separadores) - 1 - len(nuevo.xpath('following-sibling::separator')))
        # El separador original (el que queda justo antes del nuevo) está oculto: el usuario ve una sola etiqueta para las entradas.
        original = nuevo.xpath('preceding-sibling::separator[1]')[0]
        self.assertIn(original.get('invisible'), ('1', 'True', 'true'), 'El separador original queda oculto')
        self.assertNotEqual(original.get('string'), 'Novedades de nómina')

    def test_la_vista_oculta_por_defecto_importe_y_horas_de_la_lista_de_dias(self):
        pagina = self._pagina_de_dias()
        for campo in ('amount', 'number_of_hours'):
            columnas = pagina.xpath(".//field[@name='worked_days_line_ids']//field[@name='%s']" % campo)
            self.assertTrue(columnas, campo)
            self.assertEqual(columnas[0].get('optional'), 'hide', campo)
        self.assertTrue(pagina.xpath(".//field[@name='worked_days_line_ids']//field[@name='number_of_days']"), 'Los días siguen a la vista')
