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

.284 (E2a, doc 68 §12): la línea «Asistencia» ya no es el total pagado sino los DÍAS LABORADOS; el resto de los días pagados se muestra en
«Festivos trabajados», «Descansos remunerados» (fines de semana sin jornada, festivos no trabajados) y «Ajuste mes comercial». La suma de las
cuatro líneas sigue siendo ``_ne_dias_pagables`` (``_dias_pagados``) y las horas y los importes, los de .280: lo que se prueba contra «antes».

«Antes» = el comportamiento nativo: se obtiene con ``_ne_aplica_dias_por_asistencia`` en False y el botón nativo «Actualizar desde
entradas de trabajo». Valores a mano: septiembre de 2026 empieza en martes (22 días lunes a viernes, 30 comerciales); calendario de la
compañía de prueba = 40 h/semana, 8 h por día. NO EJECUTADAS en Odoo.
"""

import json
import logging
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytz
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

    CODIGOS_DESGLOSE = ('WORK100', 'CO_FEST_TRAB', 'CO_DESCANSO_REM', 'CO_AJUSTE_MES')

    def _dias_pagados(self, recibo):
        """Suma de los días de las líneas del desglose (.284): lo que antes mostraba la línea única «Asistencia»."""
        return sum(self._dias(recibo, codigo) for codigo in self.CODIGOS_DESGLOSE)

    def _horas_pagadas(self, recibo):
        return sum(self._horas(recibo, codigo) for codigo in self.CODIGOS_DESGLOSE)

    def _suma(self, lineas, campo, *codigos_tipo):
        """Suma ``campo`` de los diccionarios de línea (resultado de ``_ne_ajustar_dias_por_asistencia``) de los tipos de código ``codigos_tipo``."""
        ids = self.env['hr.work.entry.type'].search([('code', 'in', codigos_tipo)]).ids
        return sum(linea[campo] for linea in lineas if linea['work_entry_type_id'] in ids)

    def _tipo_desglose(self, nombre):
        return self.env.ref('l10n_co_nomina_electronica.hr_work_entry_type_co_%s' % nombre)

    def _limites_utc(self, recibo, dia):
        """Inicio y fin (UTC, sin zona) del día LOCAL ``dia`` en la zona del calendario del contrato."""
        zona = recibo._ne_zona_calendario()
        return tuple(zona.localize(datetime.combine(dia, momento)).astimezone(pytz.utc).replace(tzinfo=None) for momento in (time.min, time.max))

    def _entradas_del_dia(self, recibo, dia):
        inicio, fin = self._limites_utc(recibo, dia)
        return self.env['hr.work.entry'].search([
            ('contract_id', '=', recibo.contract_id.id), ('date_start', '>=', inicio), ('date_start', '<=', fin)])

    def _festivos_de_prueba(self, recibo, *dias):
        """Deja como ÚNICOS festivos globales de la compañía de prueba los días locales ``dias``. Una compañía colombiana nueva ya trae los suyos
        (Jueves y Viernes Santo, 2 y 3 de abril de 2026...) y el nativo no deja cruzar dos festivos globales de la misma compañía: se quitan
        (con sudo, dentro de la transacción) para no depender de cuáles traiga la base. El tipo de las entradas de esos días se fija a mano
        en cada prueba."""
        self.env['resource.calendar.leaves'].sudo().search([('company_id', '=', self.company.id), ('resource_id', '=', False)]).unlink()
        for dia in dias:
            inicio, fin = self._limites_utc(recibo, dia)
            self.env['resource.calendar.leaves'].create({
                'name': 'Festivo de prueba %s' % dia, 'date_from': inicio, 'date_to': fin, 'resource_id': False, 'calendar_id': False,
                'company_id': self.company.id})

    def _generar_entradas_y_festivos_de_prueba(self, recibo, *dias):
        """Genera las entradas de trabajo del recibo ANTES de crear los festivos de prueba. Sonda en staging_dev (19-nov, con rollback): un recibo
        sin calcular no tiene ninguna entrada (``hr.work.entry()`` vacío: era el fallo de estas pruebas, no un festivo de la base, cuyos festivos son
        de la compañía 1 y no cruzan con la compañía de prueba); si los festivos existen al generar, las entradas de esos días salen SIN tipo y en
        conflicto; y crear un festivo global DESPUÉS no regenera ni toca las entradas ya generadas. Así cada entrada de esos días es una asistencia
        normal (dos de 4 h) y la prueba fija a mano su tipo, sin depender de los festivos que traiga la base."""
        recibo.contract_id.generate_work_entries(recibo.date_from, recibo.date_to)
        self._festivos_de_prueba(recibo, *dias)

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
    def test_mes_completo_los_30_dias_pagados_se_desglosan_en_laborados_y_descansos(self):
        """Septiembre de 2026: 22 días lunes a viernes con entrada y 8 de fin de semana sin jornada (descansos remunerados): 22 + 8 = 30."""
        recibo = self._recibo()
        asistencia = recibo.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.code == 'WORK100')
        self.assertEqual(len(asistencia), 1)
        self.assertEqual(asistencia.number_of_days, 22.0, 'Días laborados: los de lunes a viernes con entrada')
        self.assertEqual(self._dias(recibo, 'CO_DESCANSO_REM'), 8.0, 'Descansos remunerados: sábados y domingos sin jornada')
        self.assertEqual(self._dias_pagados(recibo), 30.0)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 30.0)
        self.assertEqual(recibo._ne_dias_pagables(), 30.0)
        self.assertEqual(sorted(recibo.worked_days_line_ids.mapped('work_entry_type_id.code')), ['CO_DESCANSO_REM', 'WORK100'],
                         'Sin festivos, ajuste, ausencias ni OUT: solo laborados y descansos')
        self.assertEqual(asistencia.name, recibo._ne_tipo_asistencia().name, 'Nombre explícito, sin « (Half-Day)»')
        horas_ahora = self._horas_pagadas(recibo)
        self._como_antes(recibo)
        self.assertAlmostEqual(horas_ahora, self._horas(recibo, 'WORK100'), places=4, msg='Las horas del desglose son las del nativo')

    def test_quincena_los_dias_del_desglose_suman_15_dias_pagados(self):
        """Las dos quincenas de septiembre (1 al 15 y 16 al 30): 15 días cada una, igual a la cantidad de CO_BASICO."""
        empleado, contrato = self._contrato()
        for desde, hasta in ((date(2026, 9, 1), date(2026, 9, 15)), (date(2026, 9, 16), date(2026, 9, 30))):
            recibo = self.env['hr.payslip'].create({
                'name': 'Quincena %s' % desde, 'employee_id': empleado.id, 'contract_id': contrato.id,
                'company_id': self.company.id, 'struct_id': self.general.id, 'date_from': desde, 'date_to': hasta})
            recibo.compute_sheet()
            self.assertEqual(self._dias_pagados(recibo), 15.0, desde)
            self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 15.0, desde)
            self.assertEqual(recibo._ne_dias_pagables(), 15.0, desde)

    def test_semana_los_dias_del_desglose_suman_7_dias_pagados(self):
        """Pago semanal: 7 días calendario (sábado 2 a viernes 8 de mayo de 2026)."""
        recibo = self._recibo(date(2026, 5, 2), date(2026, 5, 8), tipo=self.tipo_semanal)
        self.assertEqual(self._dias_pagados(recibo), 7.0)
        self.assertEqual(self._dias(recibo, 'CO_AJUSTE_MES'), 0.0, 'La semana cuenta días calendario: sin ajuste de mes comercial')
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
        # Clasificación FIJA (el caso de QA): festivo no trabajado el 2 y el 3, fines de semana 4, 5, 11 y 12, y 9 días laborados. Así la prueba
        # no depende de los festivos que traiga la base. Las 30 h de «Festivo» y «Descanso» del nativo van a «Descansos remunerados».
        dias = [date(2026, 4, n) for n in range(1, 16)]
        descansos = {date(2026, 4, n) for n in (2, 3, 4, 5, 11, 12)}
        clasificacion = {
            'ausentes': set(), 'festivos_trabajados': set(), 'laborados': set(dias) - descansos, 'descansos': descansos, 'sin_entrada': set(),
            'horas_festivos_trabajados': 0.0, 'dias_reales': 15, 'dias_comerciales': 15}
        with patch.object(type(recibo), '_ne_clasificar_fechas', return_value=clasificacion):
            resultado = recibo._ne_ajustar_dias_por_asistencia(valores)
        self.assertEqual([r['work_entry_type_id'] for r in resultado],
                         [asistencia.id, self._tipo_desglose('descanso_remunerado').id])
        self.assertEqual(resultado[0]['number_of_days'], 9.0)
        self.assertAlmostEqual(resultado[0]['number_of_hours'], 80.5, places=4)
        self.assertEqual(resultado[1]['number_of_days'], 6.0)
        self.assertAlmostEqual(resultado[1]['number_of_hours'], 30.0, places=4)
        self.assertEqual(resultado[0]['name'], asistencia.name)
        self.assertEqual(self._suma(resultado, 'number_of_days', 'WORK100', 'CO_DESCANSO_REM'), 15.0)
        self.assertAlmostEqual(self._suma(resultado, 'number_of_hours', 'WORK100', 'CO_DESCANSO_REM'), 80.5 + 15.0 + 15.0, places=4)

    def test_la_asistencia_no_depende_de_las_horas_de_las_entradas(self):
        """Una entrada de más o de menos (el empleado sin entrada del 1.º de abril, 9,96 días) no cambia los días pagados."""
        asistencia = self._recibo(calcular=False)._ne_tipo_asistencia()
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15), calcular=False)
        for dias, horas in ((9.96, 73.0), (10.98, 80.5), (14.0, 103.0)):
            resultado = recibo._ne_ajustar_dias_por_asistencia(self._valores(recibo, (asistencia, dias, horas)))
            self.assertEqual(self._suma(resultado, 'number_of_days', *self.CODIGOS_DESGLOSE), 15.0, dias)
            self.assertAlmostEqual(self._suma(resultado, 'number_of_hours', *self.CODIGOS_DESGLOSE), horas, places=4,
                                   msg='Las horas son las del nativo')

    # ── ausencias ────────────────────────────────────────────────────
    def test_la_ausencia_conserva_su_linea_y_asistencia_descuenta_sus_dias(self):
        """Mes de 30 días con 5 días hábiles de vacaciones: Asistencia = 25, la línea de vacaciones intacta y en segundo lugar."""
        asistencia = self._recibo(calcular=False)._ne_tipo_asistencia()
        recibo = self._recibo(calcular=False)
        valores = self._valores(recibo, (asistencia, 17.0, 136.0), (self.tipo_vac, 5.0, 40.0))
        resultado = recibo._ne_ajustar_dias_por_asistencia(valores)
        descanso = self._tipo_desglose('descanso_remunerado')
        self.assertEqual([r['work_entry_type_id'] for r in resultado], [asistencia.id, descanso.id, self.tipo_vac.id])
        self.assertEqual(resultado[0]['number_of_days'], 17.0, 'Laborados = 25 pagables - 8 días de fin de semana')
        self.assertAlmostEqual(resultado[0]['number_of_hours'], 136.0, places=4)
        self.assertEqual(resultado[1]['number_of_days'], 8.0)
        self.assertEqual(resultado[2], valores[1], 'La línea de vacaciones no se toca')
        self.assertEqual(self._suma(resultado, 'number_of_days', 'WORK100', 'CO_DESCANSO_REM'), 25.0)
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
        # Las 8 h del festivo se conservan en «Descansos remunerados» con 0 días (los 8 días de fin de semana se recortan: no hay días pagables).
        self.assertEqual([r['work_entry_type_id'] for r in resultado], [self._tipo_desglose('descanso_remunerado').id, self.tipo_vac.id])
        self.assertEqual((resultado[0]['number_of_days'], resultado[0]['number_of_hours']), (0.0, 8.0))

    def test_vacaciones_reales_asistencia_es_lo_que_paga_co_basico(self):
        """Con una ausencia validada de verdad: Asistencia = CO_BASICO.quantity = ``_ne_dias_pagables()`` (leído de las líneas
        guardadas) = 30 - días de la línea de vacaciones; pago y suma de importes iguales a los del nativo."""
        recibo = self._recibo_con_ausencia(self.leave_vac, date(2026, 9, 16), date(2026, 9, 30))
        recibo.compute_sheet()
        dias_vac = self._dias(recibo, 'CO_VAC')
        self.assertGreaterEqual(dias_vac, 1, 'La ausencia validada no generó línea CO_VAC')
        despues = self._cifras(recibo)
        self.assertEqual(self._dias_pagados(recibo), 30.0 - dias_vac)
        self.assertEqual(self._dias(recibo, 'WORK100'), 11.0, 'Laborados: los 11 días lunes a viernes del 1 al 15')
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
        self.assertEqual(self._dias_pagados(recibo), 30.0 - dias)
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
        self.assertEqual(self._dias_pagados(recibo), 15.0)
        self.assertEqual(asistencia.number_of_days, 11.0, 'Laborados: lunes a viernes del 16 al 30; los 4 días de fin de semana son descansos')
        self.assertEqual(self._dias(recibo, 'CO_DESCANSO_REM'), 4.0)
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
        self.assertEqual(self._dias_pagados(recibo), 10.0)
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
        self.assertEqual(self._dias_pagados(recibo), 30.0)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 30.0)

    def test_solo_la_estructura_general_de_una_compania_colombiana_usa_los_dias_pagados(self):
        general = self._recibo(calcular=False)
        liquidacion = self._recibo(estructura=self.liquidacion, calcular=False)
        prima = self._recibo(estructura=self.prima, calcular=False)
        self.assertTrue(general._ne_aplica_dias_por_asistencia())
        self.assertFalse(liquidacion._ne_aplica_dias_por_asistencia())
        self.assertFalse(prima._ne_aplica_dias_por_asistencia())
        self.assertTrue(general._ne_desglosa_por_fecha(), 'El contrato trae la fuente de entradas por calendario (la única que existe)')
        self.assertFalse(liquidacion._ne_desglosa_por_fecha())
        self.assertFalse(prima._ne_desglosa_por_fecha())

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
        self.assertEqual(self._dias_pagados(recibo), 26.0)
        self.assertEqual(self._dias(recibo, 'WORK100'), 20.0, 'Laborados: 20 días lunes a viernes fuera de la incapacidad')
        self.assertEqual(self._dias(recibo, 'CO_DESCANSO_REM'), 6.0, 'Los fines de semana de la incapacidad (12 y 13) cuentan en ella, no como descanso')
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
        self.assertEqual(self._dias_pagados(recibo), 26.0)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 26.0)

    def test_maternidad_que_cruza_el_periodo_muestra_solo_los_dias_del_periodo_y_el_pago_no_cambia(self):
        """Licencia de maternidad del 25-ago al 9-sep: en el recibo de septiembre cuenta el tramo 1 al 9 = 9 días calendario (el nativo mostraba
        los 7 días hábiles con entrada: 1, 2, 3, 4, 7, 8 y 9). Asistencia = 30 - 9 = 21; el pago, igual."""
        recibo = self._recibo_con_ausencia(self.leave_lic_mat, date(2026, 8, 25), date(2026, 9, 9))
        recibo.compute_sheet()
        self.assertEqual(self._dias(recibo, 'CO_LIC_MAT'), 9.0)
        self.assertEqual(self._dias_pagados(recibo), 21.0)
        self._assert_pago_igual_antes_y_despues(recibo, ('CO_BASICO', 'CO_LIC_MAT'))

    def test_sin_ausencia_validada_la_linea_nativa_queda_igual(self):
        """Entradas de trabajo de incapacidad sin hr.leave validada (no hay fechas que contar): la línea no se reemplaza."""
        asistencia = self._recibo(calcular=False)._ne_tipo_asistencia()
        recibo = self._recibo(calcular=False)
        valores = self._valores(recibo, (asistencia, 22.0, 176.0), (self.tipo_inc_comun, 2.0, 16.0))
        resultado = recibo._ne_ajustar_dias_por_asistencia(valores)
        self.assertEqual(resultado[-1], valores[1], 'La línea de incapacidad queda al final, tal como la entrega el nativo')

    def test_un_tipo_marcado_sin_sueldo_no_se_reemplaza(self):
        """Guarda: el código de un tipo ``unpaid`` SÍ lo lee ``_ne_dias_habiles_excluidos`` de la línea; reemplazar sus días movería el pago.
        Sin la marca, la línea muestra los 4 días calendario; con la marca queda igual que la entrega el nativo."""
        recibo = self._recibo_con_ausencia(self.leave_inc_comun, date(2026, 9, 11), date(2026, 9, 14))
        asistencia = recibo._ne_tipo_asistencia()
        valores = self._valores(recibo, (asistencia, 22.0, 176.0), (self.tipo_inc_comun, 2.0, 16.0))
        self.assertEqual(recibo._ne_ajustar_dias_por_asistencia(valores)[-1]['number_of_days'], 4.0)
        self.leave_inc_comun.unpaid = True
        self.assertIn('CO_INC_COMUN', recibo._ne_codigos_tipos_no_remunerados())
        self.assertEqual(recibo._ne_ajustar_dias_por_asistencia(valores)[-1], valores[1])

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

    # ── .282: importe de las novedades con 2 decimales y «Asistencia» primera ─
    def test_la_lista_de_novedades_muestra_el_importe_con_dos_decimales(self):
        """El nativo muestra 300.000,0000: la precisión «Payroll Rate» (4) y un widget que solo recorta ceros tras un punto decimal. La vista usa
        el widget ``float`` con ``digits`` [16, 2] (solo formato)."""
        pagina = self._pagina_de_dias()
        campos = pagina.xpath(".//field[@name='input_line_ids']/*[self::list or self::tree]/field[@name='amount']")
        self.assertEqual(len(campos), 1)
        self.assertEqual(campos[0].get('widget'), 'float')
        self.assertEqual(json.loads(campos[0].get('digits')), [16, 2])

    def test_la_subvista_de_formulario_de_la_novedad_tambien_muestra_dos_decimales(self):
        pagina = self._pagina_de_dias()
        campos = pagina.xpath(".//field[@name='input_line_ids']/form//field[@name='amount']")
        self.assertEqual(len(campos), 1)
        self.assertEqual(json.loads(campos[0].get('digits')), [16, 2])

    def test_el_valor_guardado_de_una_novedad_no_cambia(self):
        """Solo presentación: una novedad de 7,333 (horas, días o pesos: el campo es mixto) se lee igual; el campo conserva su precisión."""
        recibo = self._recibo(estructura=self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_bonificacion'), calcular=False)
        entrada = self.env['hr.payslip.input'].create({
            'payslip_id': recibo.id, 'input_type_id': self.env.ref('l10n_co_nomina_electronica.input_co_bon_valor').id,
            'code': 'CO_BON_VALOR', 'amount': 7.333})
        self.assertAlmostEqual(entrada.amount, 7.333, places=4)
        self.assertEqual(self.env['hr.payslip.input']._fields['amount']._digits, 'Payroll Rate', 'El módulo no redefine la precisión del campo')

    def test_asistencia_es_la_primera_fila_de_la_pestana_con_una_incapacidad(self):
        """Incapacidad del 11 al 14 de septiembre: todas las líneas traen ``sequence`` 25 del tipo; «Asistencia» queda con una menor que la
        de todas las demás y es la primera según el orden del modelo (``payslip_id, sequence``)."""
        recibo = self._recibo_con_ausencia(self.leave_inc_comun, date(2026, 9, 11), date(2026, 9, 14))
        lineas = recibo.worked_days_line_ids
        asistencia = lineas.filtered(lambda w: w.work_entry_type_id.code == 'WORK100')
        otras = lineas - asistencia
        self.assertEqual(len(asistencia), 1)
        self.assertTrue(otras, 'Premisa: hay una línea de incapacidad')
        self.assertLess(asistencia.sequence, min(otras.mapped('sequence')))
        recibo.invalidate_recordset(['worked_days_line_ids'])
        self.assertEqual(recibo.worked_days_line_ids[0].work_entry_type_id.code, 'WORK100')

    # ── .284 (E2a): desglose por fecha ────────────────────────────────
    def test_festivos_no_trabajados_y_fines_de_semana_son_descansos_remunerados(self):
        """Abril de 2026, 1 al 15 (calendario lun-vie, 8 h): Jueves y Viernes Santo (2 y 3) con entrada de tipo Festivo. Laborados: 1, 6 a 10 y
        13 a 15 = 9 días (72 h); descansos remunerados: los 2 festivos + 4, 5, 11 y 12 = 6 días (16 h, las de las dos entradas «Festivo»); 9 + 6 =
        15. Las horas totales (88) y el pago son los del nativo."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15), calcular=False)
        festivo = self._tipo_entrada('FEST', 'Festivo', True)
        self._generar_entradas_y_festivos_de_prueba(recibo, date(2026, 4, 2), date(2026, 4, 3))
        for dia in (date(2026, 4, 2), date(2026, 4, 3)):
            entradas = self._entradas_del_dia(recibo, dia)
            self.assertTrue(entradas, 'Premisa: el calendario genera la entrada del %s' % dia)
            entradas.write({'work_entry_type_id': festivo.id})
        self._como_ahora(recibo)
        self.assertEqual(self._dias(recibo, 'WORK100'), 9.0)
        self.assertEqual(self._dias(recibo, 'CO_DESCANSO_REM'), 6.0)
        self.assertEqual(self._dias(recibo, 'CO_FEST_TRAB'), 0.0)
        self.assertEqual(self._dias(recibo, 'CO_AJUSTE_MES'), 0.0)
        self.assertEqual(self._dias_pagados(recibo), 15.0)
        self.assertAlmostEqual(self._horas(recibo, 'WORK100'), 72.0, places=4)
        self.assertAlmostEqual(self._horas(recibo, 'CO_DESCANSO_REM'), 16.0, places=4)
        self.assertFalse(recibo.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.code == 'FEST'), 'El festivo del nativo no se muestra')
        antes, despues = self._assert_pago_igual_antes_y_despues(recibo, ('CO_BASICO', 'CO_AUX_TRANS'))
        _logger.info('[.284] abril 1-15, 2 festivos no trabajados: antes=%s despues=%s', antes, despues)

    def test_festivo_con_entrada_de_asistencia_es_festivo_trabajado(self):
        """El 2 de abril el festivo queda como «Festivo» (no trabajado) y el 3 el usuario cambió el tipo de la entrada a «Asistencia» (festivo
        trabajado). Festivos trabajados: 1 día y 8 h; descansos: el 2 + 4 fines de semana = 5 días y 8 h; laborados: 9 días y 72 h (el nativo
        tenía 80 h de asistencia, 8 de ellas del 3). Las tres líneas van primero y en ese orden; 9 + 1 + 5 = 15 y las 88 h del nativo."""
        recibo = self._recibo(date(2026, 4, 1), date(2026, 4, 15), calcular=False)
        asistencia = recibo._ne_tipo_asistencia()
        festivo = self._tipo_entrada('FEST', 'Festivo', True)
        self._generar_entradas_y_festivos_de_prueba(recibo, date(2026, 4, 2), date(2026, 4, 3))
        for dia, tipo in ((date(2026, 4, 2), festivo), (date(2026, 4, 3), asistencia)):
            entradas = self._entradas_del_dia(recibo, dia)
            self.assertTrue(entradas, 'Premisa: el calendario genera la entrada del %s' % dia)
            entradas.write({'work_entry_type_id': tipo.id})
        self._como_ahora(recibo)
        self.assertEqual(recibo._ne_clasificar_fechas()['festivos_trabajados'], {date(2026, 4, 3)})
        self.assertEqual(self._dias(recibo, 'CO_FEST_TRAB'), 1.0)
        self.assertAlmostEqual(self._horas(recibo, 'CO_FEST_TRAB'), 8.0, places=4)
        self.assertEqual(self._dias(recibo, 'CO_DESCANSO_REM'), 5.0)
        self.assertAlmostEqual(self._horas(recibo, 'CO_DESCANSO_REM'), 8.0, places=4)
        self.assertEqual(self._dias(recibo, 'WORK100'), 9.0)
        self.assertAlmostEqual(self._horas(recibo, 'WORK100'), 72.0, places=4)
        self.assertEqual(self._dias_pagados(recibo), 15.0)
        self.assertAlmostEqual(self._horas_pagadas(recibo), 88.0, places=4)
        lineas = recibo.worked_days_line_ids.sorted(key=lambda w: (w.sequence, w.id))
        self.assertEqual(lineas.mapped('work_entry_type_id.code'), ['WORK100', 'CO_FEST_TRAB', 'CO_DESCANSO_REM'])
        self.assertEqual(len(set(lineas.mapped('sequence'))), 3, 'Cada línea del desglose con su propia sequence, en orden')
        self._assert_pago_igual_antes_y_despues(recibo, ('CO_BASICO', 'CO_AUX_TRANS'))

    def test_la_fecha_sin_entrada_se_paga_como_laborada_y_se_avisa(self):
        """Septiembre 1 al 15 sin la entrada del día 10 (borrada) y con la del 11 cancelada: el nativo no las cuenta (solo ``draft`` y ``validated``),
        el módulo las paga con el horario del contrato como laboradas (11 días con jornada menos 4 de fin de semana = 11) y avisa las fechas.
        Sin faltantes no hay aviso."""
        recibo = self._recibo(date(2026, 9, 1), date(2026, 9, 15))
        recibo.invalidate_recordset(['l10n_co_ne_aviso_dias'])
        self.assertFalse(recibo.l10n_co_ne_aviso_dias, 'Con todas las entradas no hay aviso')
        entradas = self._entradas_del_dia(recibo, date(2026, 9, 10))
        self.assertTrue(entradas)
        entradas.unlink()
        cancelada = self._entradas_del_dia(recibo, date(2026, 9, 11))
        self.assertTrue(cancelada)
        cancelada.write({'state': 'cancelled'})
        self._como_ahora(recibo)
        self.assertEqual(recibo._ne_clasificar_fechas()['sin_entrada'], {date(2026, 9, 10), date(2026, 9, 11)})
        self.assertEqual(self._dias(recibo, 'WORK100'), 11.0)
        self.assertEqual(self._dias_pagados(recibo), 15.0)
        self.assertAlmostEqual(self._horas(recibo, 'WORK100'), 72.0, places=4, msg='Solo las 9 entradas que existen: 9 x 8 h')
        recibo.invalidate_recordset(['l10n_co_ne_aviso_dias'])
        self.assertIn('10/09/2026', recibo.l10n_co_ne_aviso_dias)
        self.assertIn('11/09/2026', recibo.l10n_co_ne_aviso_dias)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 15.0, 'El pago no cambia: lo manda el horario')

    def test_ajuste_mes_comercial_en_la_quincena_del_16_al_31(self):
        """Agosto tiene 31 días: la quincena 16 al 31 tiene 16 fechas y se pagan 15 (el día 31 no se paga): línea «Ajuste mes comercial» de -1."""
        recibo = self._recibo(date(2026, 8, 16), date(2026, 8, 31))
        self.assertEqual(self._dias(recibo, 'CO_AJUSTE_MES'), -1.0)
        self.assertAlmostEqual(self._horas(recibo, 'CO_AJUSTE_MES'), 0.0, places=4)
        self.assertEqual(self._dias_pagados(recibo), 15.0)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 15.0)
        self._assert_pago_igual_antes_y_despues(recibo, ('CO_BASICO',))

    def test_ajuste_mes_comercial_en_la_segunda_quincena_de_febrero(self):
        """Febrero de 2026 termina el 28: 13 fechas del 16 al 28 y se pagan 15 (febrero se completa): «Ajuste mes comercial» de +2."""
        recibo = self._recibo(date(2026, 2, 16), date(2026, 2, 28))
        self.assertEqual(self._dias(recibo, 'CO_AJUSTE_MES'), 2.0)
        self.assertEqual(self._dias_pagados(recibo), 15.0)
        self.assertEqual(self._linea(recibo, 'CO_BASICO').quantity, 15.0)
        self._assert_pago_igual_antes_y_despues(recibo, ('CO_BASICO',))

    def test_sin_fuente_por_calendario_queda_una_sola_linea_como_en_282(self):
        """Guarda: con una fuente de entradas distinta de ``calendar`` (asistencias, planificación) un día sin entrada puede ser una falta y no un
        descanso; el recibo vuelve a UNA línea «Asistencia» con todos los días pagados y las horas del nativo."""
        recibo = self._recibo(calcular=False)
        asistencia = recibo._ne_tipo_asistencia()
        valores = self._valores(recibo, (asistencia, 22.0, 176.0))
        self.assertTrue(recibo._ne_desglosa_por_fecha())
        with patch.object(type(recibo), '_ne_desglosa_por_fecha', return_value=False):
            resultado = recibo._ne_ajustar_dias_por_asistencia(valores)
        self.assertEqual([(r['work_entry_type_id'], r['number_of_days'], r['number_of_hours']) for r in resultado], [(asistencia.id, 30.0, 176.0)])

    def test_la_fecha_de_una_entrada_es_la_local_del_calendario(self):
        """Una entrada de 20:00 a 23:00 (hora de Bogotá) del sábado 12 de septiembre se guarda en UTC como 01:00 a 04:00 del domingo 13: cuenta
        como trabajo del sábado (laborada, fuera del horario) y el domingo queda de descanso."""
        recibo = self._recibo(calcular=False)
        recibo.contract_id.resource_calendar_id.tz = 'America/Bogota'
        zona = pytz.timezone('America/Bogota')
        inicio = zona.localize(datetime(2026, 9, 12, 20, 0)).astimezone(pytz.utc).replace(tzinfo=None)
        entrada = self.env['hr.work.entry'].create({
            'name': 'Turno nocturno', 'employee_id': recibo.employee_id.id, 'contract_id': recibo.contract_id.id,
            'work_entry_type_id': recibo._ne_tipo_asistencia().id, 'date_start': inicio, 'date_stop': inicio + timedelta(hours=3)})
        self.assertEqual(entrada.state, 'draft', 'Premisa: la entrada creada a mano no queda en conflicto')
        clasificacion = recibo._ne_clasificar_fechas()
        self.assertIn(date(2026, 9, 12), clasificacion['laborados'])
        self.assertNotIn(date(2026, 9, 13), clasificacion['laborados'])
        self.assertIn(date(2026, 9, 13), clasificacion['descansos'])

    def test_la_vista_muestra_el_aviso_de_entradas_antes_de_la_lista_de_dias(self):
        pagina = self._pagina_de_dias()
        campos = pagina.xpath("./div//field[@name='l10n_co_ne_aviso_dias']")
        self.assertEqual(len(campos), 1)
        self.assertTrue(campos[0].xpath("ancestor::div[1]/following-sibling::field[@name='worked_days_line_ids']"), 'Va antes de la lista de días')

    def test_los_tipos_del_desglose_son_propios_y_pagados(self):
        """Los tres tipos nuevos existen con su código, no son «sin sueldo» (si lo fueran ``_ne_dias_pagables`` los descontaría) y sus líneas son
        pagadas (``is_paid``: el tipo no está en los no pagados de la estructura, enterprise hr_payslip_worked_days.py:28-34)."""
        recibo = self._recibo()
        no_remunerados = recibo._ne_codigos_tipos_no_remunerados()
        for nombre, codigo in (('festivo_trabajado', 'CO_FEST_TRAB'), ('descanso_remunerado', 'CO_DESCANSO_REM'),
                               ('ajuste_mes_comercial', 'CO_AJUSTE_MES')):
            tipo = self._tipo_desglose(nombre)
            self.assertEqual(tipo.code, codigo)
            self.assertNotIn(codigo, no_remunerados)
            self.assertNotIn(tipo, recibo.struct_id.unpaid_work_entry_type_ids)
        self.assertTrue(self._dias(recibo, 'CO_DESCANSO_REM'), 'Premisa: septiembre trae una línea de descansos')
        self.assertEqual(recibo._ne_dias_pagables(), 30.0, 'Las líneas del desglose no se descuentan del básico')
        self.assertTrue(all(recibo.worked_days_line_ids.mapped('is_paid')))

    def test_el_residuo_nunca_deja_dias_negativos_y_las_sumas_se_conservan(self):
        """Aritmética del reparto con clasificaciones fijas: Σ días = pagables y Σ horas = las del nativo en todos los casos; las líneas que no son
        el ajuste nunca tienen días negativos (descansos de más en un periodo casi todo de ausencias: se recortan primero los descansos)."""
        recibo = self._recibo(calcular=False)
        asistencia = recibo._ne_tipo_asistencia()
        casos = (  # pagables, descansos, festivos trabajados, fechas reales, días comerciales
            (15.0, 4, 0, 15, 15), (1.0, 4, 0, 15, 15), (0.0, 2, 0, 16, 15), (10.0, 4, 3, 16, 15), (15.0, 4, 0, 13, 15), (15.0, 4, 2, 15, 15))
        for pagables, descansos, festivos, reales, comerciales in casos:
            clasificacion = {
                'descansos': {date(2026, 9, 1) + timedelta(days=n) for n in range(descansos)},
                'festivos_trabajados': {date(2026, 9, 20) + timedelta(days=n) for n in range(festivos)},
                'horas_festivos_trabajados': 8.0 * festivos, 'dias_reales': reales, 'dias_comerciales': comerciales}
            lineas = recibo._ne_desglose_por_fecha(asistencia, pagables, 100.0, 24.0, clasificacion)
            caso = (pagables, descansos, festivos, reales, comerciales)
            self.assertAlmostEqual(sum(dias for _tipo, dias, _horas in lineas), pagables, places=6, msg=caso)
            self.assertAlmostEqual(sum(horas for _tipo, _dias, horas in lineas), 124.0, places=6, msg=caso)
            for tipo, dias, _horas in lineas:
                if tipo.code != 'CO_AJUSTE_MES':
                    self.assertGreaterEqual(dias, 0.0, msg=(caso, tipo.code))
