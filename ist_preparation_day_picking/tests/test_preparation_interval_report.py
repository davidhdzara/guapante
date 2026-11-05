# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.api import call_kw
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.models.const_preparation import (
    REPORTS_START_DATE_PARAM_KEY,
)

from .test_preparation_day_product_claim import TestPreparationDayProductClaim


@tagged('post_install', '-at_install')
class TestPreparationIntervalReport(TestPreparationDayProductClaim):
    """Fase 2, commit 5/7 (Tech Lead, 2026-11-04) — Reportes 3/4/5
    (modelo compartido guapante.preparation.interval.report), el
    archivo de mayor riesgo del commit: cubre el filtro de solo
    cerrados, reports_start_date, y las 4 condiciones de la razón
    ponderada (SUM/SUM vía read_group override, condiciones de Tech
    Lead 2026-11-04).

    product_tmpl_id en guapante.preparation.interval es related sobre
    claim_id.product_tmpl_id (store=True, sin inverse) — para fijarlo
    en un intervalo de fixture hace falta un claim real de ese
    producto, nunca escribirlo directo en el intervalo."""

    def setUp(self):
        super().setUp()
        self.Report = self.env['guapante.preparation.interval.report']
        self.Day = self.env['guapante.preparation.day']

    def _far_today(self):
        """Fecha lejana para fixtures de sesión (Tech Lead, endurecimiento
        de tests, 2026-11-04) — NUNCA context_today real: hoy puede ya
        tener una sesión real (ej. una prueba en vivo de David en
        staging_dev) y _check_unique_date no permite una segunda para la
        misma fecha. +200 días — offset distinto al de
        test_preparation_operator_report.py (+210) para que los
        archivos de reportes no puedan pisarse entre sí (el tercer
        offset, +220, era de test_preparation_product_demand_report.py,
        quitado en la Tarea 3, Tech Lead/David, 2026-11-05)."""
        return fields.Date.add(
            fields.Date.context_today(self.env['sale.order']), days=200,
        )

    def _session(self, date):
        return self.Day.create({'date': date})

    def _claim(self, session, product):
        return self.Claim.sudo().create({
            'wizard_id': session.id,
            'product_tmpl_id': product.product_tmpl_id.id,
        })

    def _interval(self, claim, kind='working', employee=None, start_dt=None,
                  end_dt=None, duration_s=None, kg_done=0.0, lines_done=0,
                  first_weigh_dt=None):
        vals = {
            'wizard_id': claim.wizard_id.id,
            'claim_id': claim.id,
            'employee_id': employee.id if employee else False,
            'kind': kind,
            'start_dt': start_dt,
            'last_touched_dt': end_dt or start_dt,
            'end_dt': end_dt,
            'duration_s': duration_s,
            'kg_done': kg_done,
            'lines_done': lines_done,
            'first_weigh_dt': first_weigh_dt,
        }
        return self.Interval.sudo().create(vals)

    # ── Solo intervalos cerrados ──

    def test_open_interval_never_appears(self):
        today = self._far_today()
        session = self._session(today)
        claim = self._claim(session, self.product_weight)
        now = fields.Datetime.now()
        self._interval(
            claim, 'working', self.operator_a, start_dt=now, end_dt=None,
        )

        rows = self.Report.sudo().search_read(
            [('wizard_id', '=', session.id)], ['id'],
        )
        self.assertFalse(rows)

    def test_closed_interval_appears(self):
        today = self._far_today()
        session = self._session(today)
        claim = self._claim(session, self.product_weight)
        now = fields.Datetime.now()
        self._interval(
            claim, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=60), end_dt=now, duration_s=60,
        )

        rows = self.Report.sudo().search_read(
            [('wizard_id', '=', session.id)], ['id', 'duration_s'],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['duration_s'], 60)

    # ── reports_start_date (sobre start_dt) ──

    def test_reports_start_date_filters_on_start_dt(self):
        cutoff = fields.Datetime.now()
        self.env['ir.config_parameter'].sudo().set_param(
            REPORTS_START_DATE_PARAM_KEY, str(cutoff.date()),
        )
        today = self._far_today()
        session = self._session(today)
        claim = self._claim(session, self.product_weight)
        before = cutoff - timedelta(days=1)
        after = cutoff + timedelta(hours=1)
        self._interval(
            claim, 'working', self.operator_a,
            start_dt=before, end_dt=before + timedelta(seconds=30),
            duration_s=30,
        )
        self._interval(
            claim, 'working', self.operator_a,
            start_dt=after, end_dt=after + timedelta(seconds=50),
            duration_s=50,
        )

        rows = self.Report.sudo().search_read(
            [('wizard_id', '=', session.id)], ['duration_s'],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['duration_s'], 50)

    # ── duration_s / duration_avg_s / kind ──

    def test_duration_sum_and_avg_grouped_by_kind(self):
        today = self._far_today()
        session = self._session(today)
        claim = self._claim(session, self.product_weight)
        now = fields.Datetime.now()
        self._interval(
            claim, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=100), end_dt=now, duration_s=100,
        )
        self._interval(
            claim, 'working', self.operator_b,
            start_dt=now - timedelta(seconds=200), end_dt=now, duration_s=200,
        )
        self._interval(
            claim, 'stopped', employee=None,
            start_dt=now - timedelta(seconds=30), end_dt=now, duration_s=30,
        )

        groups = self.Report.sudo().read_group(
            [('wizard_id', '=', session.id)],
            ['duration_s:sum', 'duration_avg_s:avg'], ['kind'],
        )
        by_kind = {g['kind']: g for g in groups}
        self.assertEqual(by_kind['working']['duration_s'], 300)
        self.assertEqual(by_kind['working']['duration_avg_s'], 150)
        self.assertEqual(by_kind['stopped']['duration_s'], 30)
        self.assertEqual(by_kind['stopped']['duration_avg_s'], 30)

    # ── time_to_first_weigh_s ──

    def test_time_to_first_weigh_null_when_never_weighed(self):
        """Working sin pesaje (first_weigh_dt vacío): NULL, no 0 — un
        avg sobre NULLs los ignora, no los trata como cero."""
        today = self._far_today()
        session = self._session(today)
        claim = self._claim(session, self.product_weight)
        now = fields.Datetime.now()
        self._interval(
            claim, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=40), end_dt=now, duration_s=40,
            first_weigh_dt=None,
        )
        self._interval(
            claim, 'working', self.operator_b,
            start_dt=now - timedelta(seconds=40), end_dt=now, duration_s=40,
            first_weigh_dt=now - timedelta(seconds=30),
        )

        groups = self.Report.sudo().read_group(
            [('wizard_id', '=', session.id)], ['time_to_first_weigh_s:avg'], [],
        )
        self.assertEqual(groups[0]['time_to_first_weigh_s'], 10)

    # ── time_without_lines_s ──

    def test_time_without_lines_only_counts_working_with_zero_lines(self):
        today = self._far_today()
        session = self._session(today)
        claim = self._claim(session, self.product_weight)
        now = fields.Datetime.now()
        self._interval(
            claim, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=80), end_dt=now, duration_s=80,
            lines_done=0,
        )
        self._interval(
            claim, 'working', self.operator_b,
            start_dt=now - timedelta(seconds=50), end_dt=now, duration_s=50,
            lines_done=3,
        )
        self._interval(
            claim, 'stopped', employee=None,
            start_dt=now - timedelta(seconds=20), end_dt=now, duration_s=20,
            lines_done=0,
        )

        groups = self.Report.sudo().read_group(
            [('wizard_id', '=', session.id)], ['time_without_lines_s:sum'], [],
        )
        self.assertEqual(groups[0]['time_without_lines_s'], 80)

    # ── NULL ratio para stopped / denominador 0 ──

    def test_time_per_kg_and_box_null_for_stopped_or_zero_denominator(self):
        today = self._far_today()
        session = self._session(today)
        claim = self._claim(session, self.product_weight)
        now = fields.Datetime.now()
        stopped = self._interval(
            claim, 'stopped', employee=None,
            start_dt=now - timedelta(seconds=10), end_dt=now, duration_s=10,
            kg_done=5.0, lines_done=2,
        )
        zero_denom = self._interval(
            claim, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=10), end_dt=now, duration_s=10,
            kg_done=0.0, lines_done=0,
        )

        rows = self.Report.sudo().search_read(
            [('id', 'in', [stopped.id, zero_denom.id])],
            ['time_per_kg_s', 'time_per_box_s'],
        )
        for row in rows:
            self.assertFalse(row['time_per_kg_s'])
            self.assertFalse(row['time_per_box_s'])

    # ── Razón ponderada SUM/SUM (condiciones de Tech Lead, 2026-11-04) ──
    #
    # Fixture de las 4 pruebas siguientes, point por point en relación al
    # ejemplo que dio Tech Lead ("10 s/1 kg y 100 s/10 kg dan 110/11=10,
    # no el AVG de razones (55)"): las razones por fila de ese ejemplo
    # son 10/1=10 y 100/10=10 — AVG(10,10)=10, IGUAL al resultado
    # ponderado (110/11=10): ese ejemplo no demuestra ningún sesgo (y
    # "55" es en realidad AVG(10,100), promediar los SEGUNDOS crudos
    # ignorando el kg — un error distinto, no "AVG de razones"). Se usa
    # acá un ejemplo que sí expone el sesgo: 10 s/1 kg (razón 10) y
    # 100 s/50 kg (razón 2) — ponderado = 110/51 ≈ 2.157, mientras que
    # el AVG de razones por fila sería (10+2)/2 = 6. Este punto se
    # reporta a Tech Lead junto con el hash de 5/7, sin "corregir" en
    # silencio su ejemplo.

    def _build_weighted_ratio_fixture(self):
        """2 intervalos working con lines_done>0 y kg_done>0, cada uno
        en su propio empleado+producto+jornada, para poder probar la
        ponderación total Y por cada una de las 3 dimensiones de
        agrupación (operario, producto, jornada) con el MISMO fixture."""
        day1 = self._far_today()
        day2 = fields.Date.add(day1, days=1)
        session1 = self._session(day1)
        session2 = self._session(day2)
        claim1 = self._claim(session1, self.product_weight)
        claim2 = self._claim(session2, self.product_unit)
        now = fields.Datetime.now()
        row1 = self._interval(
            claim1, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=10), end_dt=now, duration_s=10,
            kg_done=1.0, lines_done=1,
        )
        row2 = self._interval(
            claim2, 'working', self.operator_b,
            start_dt=now - timedelta(seconds=100), end_dt=now, duration_s=100,
            kg_done=50.0, lines_done=50,
        )
        return row1, row2

    def test_weighted_ratio_total_is_sum_over_sum_not_avg_of_ratios(self):
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        groups = self.Report.sudo().read_group(
            domain, ['time_per_kg_s:avg'], [],
        )
        self.assertAlmostEqual(groups[0]['time_per_kg_s'], 110 / 51, places=6)
        # El AVG de razones por fila (10 + 2) / 2 = 6 sería el valor
        # sesgado que Tech Lead rechazó explícitamente.
        self.assertNotAlmostEqual(groups[0]['time_per_kg_s'], 6, places=3)

    def test_weighted_ratio_grouped_by_employee_does_not_mix_groups(self):
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        groups = self.Report.sudo().read_group(
            domain, ['time_per_kg_s:avg'], ['employee_id'],
        )
        by_employee = {g['employee_id'][0]: g['time_per_kg_s'] for g in groups}
        self.assertAlmostEqual(by_employee[self.operator_a.id], 10.0, places=6)
        self.assertAlmostEqual(by_employee[self.operator_b.id], 2.0, places=6)

    def test_weighted_ratio_grouped_by_product_does_not_mix_groups(self):
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        groups = self.Report.sudo().read_group(
            domain, ['time_per_kg_s:avg'], ['product_tmpl_id'],
        )
        by_product = {
            g['product_tmpl_id'][0]: g['time_per_kg_s'] for g in groups
        }
        self.assertAlmostEqual(
            by_product[self.product_weight.product_tmpl_id.id], 10.0, places=6,
        )
        self.assertAlmostEqual(
            by_product[self.product_unit.product_tmpl_id.id], 2.0, places=6,
        )

    def test_weighted_ratio_grouped_by_jornada_does_not_mix_groups(self):
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        groups = self.Report.sudo().read_group(
            domain, ['time_per_kg_s:avg'], ['date:day'],
        )
        self.assertEqual(len(groups), 2)
        by_ratio = sorted(g['time_per_kg_s'] for g in groups)
        self.assertAlmostEqual(by_ratio[0], 2.0, places=6)
        self.assertAlmostEqual(by_ratio[1], 10.0, places=6)

    def test_weighted_ratio_per_box_is_sum_over_sum(self):
        """Mismo patrón que time_per_kg_s pero con lines_done como
        denominador (Reporte 5)."""
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        groups = self.Report.sudo().read_group(
            domain, ['time_per_box_s:avg'], [],
        )
        self.assertAlmostEqual(groups[0]['time_per_box_s'], 110 / 51, places=6)

    def test_weighted_ratio_grouped_by_day_and_employee_does_not_mix_groups(self):
        """Tarea 12 (Tech Lead/David, 2026-11-05): el gráfico "Tiempo
        por operario" expone Seg/caja y Seg/kg como medidas, bajo la
        agrupación día × operario (la del gráfico: date:day luego
        employee_id) — fixture de 2 operarios y 2 días, con DOS
        intervalos en la MISMA celda (día1/operario_a) para probar que
        ahí también es SUM/SUM y no el promedio sesgado de las 2
        razones por fila."""
        day1 = self._far_today()
        day2 = fields.Date.add(day1, days=1)
        session1 = self._session(day1)
        session2 = self._session(day2)
        claim1 = self._claim(session1, self.product_weight)
        claim2 = self._claim(session2, self.product_weight)
        now = fields.Datetime.now()
        # día1/operario_a: 2 intervalos en la MISMA celda — 110/51,
        # nunca avg(10, 2)=6.
        self._interval(
            claim1, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=10), end_dt=now, duration_s=10,
            kg_done=1.0, lines_done=1,
        )
        self._interval(
            claim1, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=100), end_dt=now, duration_s=100,
            kg_done=50.0, lines_done=50,
        )
        # día1/operario_b: 1 intervalo — razón=10.
        self._interval(
            claim1, 'working', self.operator_b,
            start_dt=now - timedelta(seconds=30), end_dt=now, duration_s=30,
            kg_done=3.0, lines_done=3,
        )
        # día2/operario_a: 1 intervalo — razón=10.
        self._interval(
            claim2, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=40), end_dt=now, duration_s=40,
            kg_done=4.0, lines_done=4,
        )
        # día2/operario_b: 1 intervalo — razón=10.
        self._interval(
            claim2, 'working', self.operator_b,
            start_dt=now - timedelta(seconds=50), end_dt=now, duration_s=50,
            kg_done=5.0, lines_done=5,
        )

        # Cada sesión es YA una sola jornada (date fijo por sesión) —
        # agrupar por sesión + employee_id prueba exactamente la misma
        # celda día×operario que el gráfico, sin depender del formato
        # de etiqueta que read_group use para 'date:day' (ej. "05 Nov
        # 2026" vs ISO — no es parte del contrato que este test deba
        # fijar).
        for measure in ('time_per_box_s', 'time_per_kg_s'):
            with self.subTest(measure=measure):
                groups_day1 = self.Report.sudo().read_group(
                    [('wizard_id', '=', session1.id)],
                    [f'{measure}:avg'], ['employee_id'],
                )
                by_employee_day1 = {
                    g['employee_id'][0]: g[measure] for g in groups_day1
                }
                self.assertAlmostEqual(
                    by_employee_day1[self.operator_a.id], 110 / 51, places=6,
                )
                self.assertNotAlmostEqual(
                    by_employee_day1[self.operator_a.id], 6, places=3,
                )
                self.assertAlmostEqual(
                    by_employee_day1[self.operator_b.id], 10.0, places=6,
                )

                groups_day2 = self.Report.sudo().read_group(
                    [('wizard_id', '=', session2.id)],
                    [f'{measure}:avg'], ['employee_id'],
                )
                by_employee_day2 = {
                    g['employee_id'][0]: g[measure] for g in groups_day2
                }
                self.assertAlmostEqual(
                    by_employee_day2[self.operator_a.id], 10.0, places=6,
                )
                self.assertAlmostEqual(
                    by_employee_day2[self.operator_b.id], 10.0, places=6,
                )

                # Y la MISMA invariante con los dos ejes juntos
                # (date:day, employee_id) — el agrupamiento real del
                # gráfico — sin inspeccionar el formato de la etiqueta
                # de fecha, solo que salgan 4 celdas y que la celda
                # mixta no se pierda/colapse mal.
                groups_both = self.Report.sudo().read_group(
                    [('wizard_id', 'in', [session1.id, session2.id])],
                    [f'{measure}:avg'], ['date:day', 'employee_id'],
                    lazy=False,
                )
                self.assertEqual(len(groups_both), 4)
                values = sorted(g[measure] for g in groups_both)
                self.assertAlmostEqual(values[0], 110 / 51, places=6)
                self.assertAlmostEqual(values[1], 10.0, places=6)
                self.assertAlmostEqual(values[2], 10.0, places=6)
                self.assertAlmostEqual(values[3], 10.0, places=6)

    def test_weighted_ratio_via_web_read_group_list_path(self):
        """Condición 2 de Tech Lead: el camino de LISTA (web_read_group
        → _web_read_group → read_group, confirmado passthrough leyendo
        el core) debe devolver el mismo valor ponderado que el pivote,
        no un camino distinto ni el AVG sesgado."""
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        result = self.Report.sudo().web_read_group(
            domain, ['time_per_kg_s:avg'], [],
        )
        self.assertEqual(result['length'], 1)
        self.assertAlmostEqual(
            result['groups'][0]['time_per_kg_s'], 110 / 51, places=6,
        )

    def test_auxiliary_forced_fields_stripped_unless_requested(self):
        """Condición 4 de Tech Lead: duration_s/kg_done que el override
        fuerza a sumar para calcular la razón NO deben aparecer en el
        resultado si el cliente no los pidió — y SÍ deben aparecer,
        con su propio valor real, si el cliente los pidió junto con la
        razón."""
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        only_ratio = self.Report.sudo().read_group(
            domain, ['time_per_kg_s:avg'], [],
        )
        self.assertNotIn('duration_s', only_ratio[0])
        self.assertNotIn('kg_done', only_ratio[0])

        with_both = self.Report.sudo().read_group(
            domain, ['time_per_kg_s:avg', 'duration_s:sum', 'kg_done:sum'], [],
        )
        self.assertIn('duration_s', with_both[0])
        self.assertEqual(with_both[0]['duration_s'], 110)
        self.assertEqual(with_both[0]['kg_done'], 51.0)
        self.assertAlmostEqual(with_both[0]['time_per_kg_s'], 110 / 51, places=6)

    def test_read_group_without_ratio_measure_is_unaffected(self):
        """Si nadie pide time_per_kg_s/time_per_box_s, el override debe
        ser un passthrough transparente — sin forzar nada ni tocar el
        resultado."""
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        groups = self.Report.sudo().read_group(
            domain, ['duration_s:sum'], [],
        )
        self.assertEqual(groups[0]['duration_s'], 110)
        self.assertNotIn('time_per_kg_s', groups[0])

    # ── Bug real de producción (Tech Lead, 2026-11-04): el camino de
    #    kwargs del cliente, NUNCA el posicional de los tests de arriba ──
    #
    # David reventó "Tiempo por producto" en staging_dev con TypeError:
    # read_group() got an unexpected keyword argument 'fields' — el
    # override nombraba su parámetro `fields_list`, pero el pivote/la
    # lista agrupada del cliente llaman por kwargs (domain=, fields=,
    # groupby=, lazy=...) vía odoo.api.call_kw, nunca posicional. TODOS
    # los tests de arriba llaman `.read_group(domain, [...], [...])`
    # posicional — por eso nunca lo vieron, aunque prueban bien la
    # lógica de la razón ponderada. Estos 3 tests reproducen el camino
    # REAL (call_kw con kwargs) para que un regreso de este bug (o uno
    # igual en otro método) sí truene la suite.

    def test_read_group_via_call_kw_kwargs_path_matches_pivot(self):
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        result = call_kw(
            self.Report.sudo(), 'read_group', [],
            {
                'domain': domain, 'fields': ['time_per_kg_s:avg'],
                'groupby': [], 'lazy': False,
            },
        )
        self.assertAlmostEqual(result[0]['time_per_kg_s'], 110 / 51, places=6)

    def test_read_group_via_call_kw_kwargs_path_plain_measure_grouped(self):
        """Mismo camino de kwargs, pero sin medida ponderada —
        confirma que el passthrough (no solo la rama de la razón)
        también sobrevive a kwargs, agrupado."""
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        result = call_kw(
            self.Report.sudo(), 'read_group', [],
            {
                'domain': domain, 'fields': ['duration_s:sum'],
                'groupby': ['employee_id'], 'lazy': False,
            },
        )
        self.assertEqual(len(result), 2)

    def test_web_read_group_via_call_kw_kwargs_path(self):
        """Condición 2 de Tech Lead, pero por kwargs — el camino de
        lista agrupada con fila de total que usa el cliente real
        (orm.webReadGroup → web_read_group → _web_read_group →
        read_group)."""
        row1, row2 = self._build_weighted_ratio_fixture()
        domain = [('id', 'in', [row1.id, row2.id])]

        result = call_kw(
            self.Report.sudo(), 'web_read_group', [],
            {
                'domain': domain, 'fields': ['time_per_kg_s:avg'],
                'groupby': [], 'lazy': False,
            },
        )
        self.assertEqual(result['length'], 1)
        self.assertAlmostEqual(
            result['groups'][0]['time_per_kg_s'], 110 / 51, places=6,
        )

    def test_duration_s_renamed_to_tiempo_trabajado(self):
        """Tarea 3 (Tech Lead/David, 2026-11-05): "Tiempo (s)" →
        "Tiempo trabajado (s)", con ayuda explicando que también
        cubre 'stopped' (Reporte 3). Guarda barata contra un revert
        accidental de la etiqueta."""
        field = self.Report._fields['duration_s']
        self.assertEqual(field.string, 'Tiempo trabajado (s)')
        self.assertTrue(field.help)

    def _assert_kg_or_box_graph(self, view_xmlid, ratio_field):
        """Tarea 14 (Tech Lead/David, 2026-11-05) — texto aprobado:
        "Barras verticales, eje X = producto (nombre), eje Y = Seg/kg
        (razón ponderada)... Una barra por producto, ordenadas de
        mayor a menor (el más lento por kg primero). Una sola serie,
        sin leyenda; operario NO agrupa por defecto." Verifica: bar +
        order="DESC" en el arch (atributo confirmado en el fuente real
        de Odoo 18 — web/static/src/views/graph/graph_arch_parser.js,
        ORDERS=["ASC","DESC",...]; graph_model.js ordena los grupos
        por la suma de la medida activa), único groupby no-measure
        (product_tmpl_id), y la razón (time_per_kg_s/time_per_box_s)
        como ÚLTIMA medida declarada (default), con duration_s/
        kg_done/lines_done también declaradas (adición de Tech Lead,
        medidas seleccionables)."""
        import xml.etree.ElementTree as ET

        view = self.env.ref(view_xmlid)
        root = ET.fromstring(view.arch)
        self.assertEqual(root.get('type'), 'bar')
        self.assertEqual(root.get('order'), 'DESC')
        group_fields = [
            f.get('name') for f in root.findall('field')
            if f.get('type') != 'measure'
        ]
        self.assertEqual(group_fields, ['product_tmpl_id'])
        measure_fields = [
            f.get('name') for f in root.findall('field')
            if f.get('type') == 'measure'
        ]
        self.assertEqual(
            measure_fields,
            ['duration_s', 'kg_done', 'lines_done', ratio_field],
            f'{ratio_field} debe ser la ÚLTIMA medida declarada (el '
            'cliente usa el último <field type="measure"> como medida '
            'por defecto).',
        )

    def test_report_4_kg_graph_bar_desc_product_only(self):
        self._assert_kg_or_box_graph(
            'ist_preparation_day_picking.view_preparation_interval_report_kg_graph',
            'time_per_kg_s',
        )

    def test_report_5_box_graph_bar_desc_product_only(self):
        self._assert_kg_or_box_graph(
            'ist_preparation_day_picking.view_preparation_interval_report_box_graph',
            'time_per_box_s',
        )

    def _assert_action_groups_by_product_only(self, action_xmlid, ratio_field):
        """Tarea 14: operario NO agrupa por defecto (queda como filtro
        manual, group_employee sigue en el buscador compartido) — ni
        en pivot_row_groupby ni como search_default_group_employee.
        pivot_measures debe traer las mismas 4 medidas que el gráfico
        (adición de Tech Lead)."""
        from odoo.tools.safe_eval import safe_eval

        action = self.env.ref(action_xmlid)
        context = safe_eval(action.context or '{}')
        self.assertEqual(context['pivot_row_groupby'], ['product_tmpl_id'])
        self.assertEqual(
            set(context['pivot_measures']),
            {'duration_s', 'kg_done', 'lines_done', ratio_field},
        )
        self.assertNotIn('search_default_group_employee', context)
        self.assertNotIn('search_default_group_product', context)

    def test_report_4_action_groups_by_product_only(self):
        self._assert_action_groups_by_product_only(
            'ist_preparation_day_picking.action_preparation_interval_report_4',
            'time_per_kg_s',
        )

    def test_report_5_action_groups_by_product_only(self):
        self._assert_action_groups_by_product_only(
            'ist_preparation_day_picking.action_preparation_interval_report_5',
            'time_per_box_s',
        )

    def _eval_search_filter_domain(self, filter_name):
        """Tarea 13 (Tech Lead/David, 2026-11-05) — parsea el arch REAL
        del buscador compartido (3/4/5) y evalúa el domain del filtro
        con el MISMO contexto estándar que Odoo expone a cualquier
        domain de vista (context_today/relativedelta, ver odoo/tools/
        view_validation.py) — así la prueba cubre exactamente el
        string que se va a desplegar, no una reimplementación
        paralela de la fórmula."""
        import xml.etree.ElementTree as ET

        from dateutil.relativedelta import relativedelta
        from odoo.tools.safe_eval import safe_eval

        view = self.env.ref(
            'ist_preparation_day_picking.view_preparation_interval_report_search'
        )
        root = ET.fromstring(view.arch)
        node = root.find(f".//filter[@name='{filter_name}']")
        self.assertIsNotNone(node, f'filtro {filter_name!r} no existe en el arch.')
        eval_context = {
            'context_today': lambda: fields.Date.context_today(self.env.user),
            'relativedelta': relativedelta,
        }
        return safe_eval(node.get('domain'), eval_context)

    def test_filter_today_domain_is_exact_context_today(self):
        today = fields.Date.context_today(self.env.user).strftime('%Y-%m-%d')
        self.assertEqual(
            self._eval_search_filter_domain('filter_today'),
            [('date', '=', today)],
        )

    def test_filter_yesterday_domain_is_context_today_minus_1(self):
        from dateutil.relativedelta import relativedelta
        yesterday = (
            fields.Date.context_today(self.env.user) - relativedelta(days=1)
        ).strftime('%Y-%m-%d')
        self.assertEqual(
            self._eval_search_filter_domain('filter_yesterday'),
            [('date', '=', yesterday)],
        )

    def test_filter_last_7_days_domain_is_context_today_minus_7(self):
        from dateutil.relativedelta import relativedelta
        start = (
            fields.Date.context_today(self.env.user) - relativedelta(days=7)
        ).strftime('%Y-%m-%d')
        self.assertEqual(
            self._eval_search_filter_domain('filter_last_7_days'),
            [('date', '>=', start)],
        )

    def test_filter_this_month_domain_starts_on_day_1(self):
        start = fields.Date.context_today(self.env.user).replace(
            day=1,
        ).strftime('%Y-%m-%d')
        self.assertEqual(
            self._eval_search_filter_domain('filter_this_month'),
            [('date', '>=', start)],
        )

    def test_filter_last_month_domain_excludes_this_month(self):
        from dateutil.relativedelta import relativedelta
        this_month_start = fields.Date.context_today(self.env.user).replace(day=1)
        last_month_start = (this_month_start - relativedelta(months=1))
        self.assertEqual(
            self._eval_search_filter_domain('filter_last_month'),
            [
                ('date', '>=', last_month_start.strftime('%Y-%m-%d')),
                ('date', '<', this_month_start.strftime('%Y-%m-%d')),
            ],
        )

    def _assert_action_default_filter(self, action_xmlid, filter_key):
        from odoo.tools.safe_eval import safe_eval

        action = self.env.ref(action_xmlid)
        context = safe_eval(action.context or '{}')
        self.assertEqual(context.get(filter_key), 1)

    def test_report_2_defaults_to_last_7_days(self):
        self._assert_action_default_filter(
            'ist_preparation_day_picking.action_preparation_interval_report_2',
            'search_default_filter_last_7_days',
        )

    def test_report_3_defaults_to_today(self):
        self._assert_action_default_filter(
            'ist_preparation_day_picking.action_preparation_interval_report_3',
            'search_default_filter_today',
        )

    def test_report_4_defaults_to_today(self):
        self._assert_action_default_filter(
            'ist_preparation_day_picking.action_preparation_interval_report_4',
            'search_default_filter_today',
        )

    def test_report_5_defaults_to_today(self):
        self._assert_action_default_filter(
            'ist_preparation_day_picking.action_preparation_interval_report_5',
            'search_default_filter_today',
        )

    def test_categ_id_groups_intervals_by_category(self):
        """Tarea 13: categ_id = product.template.categ_id ESTÁNDAR,
        agregado al _table_query vía LEFT JOIN product_template — dos
        productos en categorías distintas deben separarse al agrupar
        por categ_id, cada uno con su propia suma."""
        categ_a = self.env['product.category'].create({'name': 'Categoría A (test)'})
        categ_b = self.env['product.category'].create({'name': 'Categoría B (test)'})
        self.product_weight.product_tmpl_id.categ_id = categ_a.id
        self.product_unit.product_tmpl_id.categ_id = categ_b.id

        day = self._far_today()
        session = self._session(day)
        claim_a = self._claim(session, self.product_weight)
        claim_b = self._claim(session, self.product_unit)
        now = fields.Datetime.now()
        self._interval(
            claim_a, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=10), end_dt=now, duration_s=10,
            kg_done=1.0, lines_done=1,
        )
        self._interval(
            claim_b, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=20), end_dt=now, duration_s=20,
            kg_done=2.0, lines_done=2,
        )

        result = call_kw(
            self.Report.sudo(), 'read_group', [],
            {
                'domain': [('wizard_id', '=', session.id)],
                'fields': ['duration_s:sum'],
                'groupby': ['categ_id'], 'lazy': False,
            },
        )
        by_categ = {g['categ_id'][0]: g['duration_s'] for g in result}
        self.assertEqual(by_categ[categ_a.id], 10)
        self.assertEqual(by_categ[categ_b.id], 20)

    def test_product_search_matches_by_name_or_internal_reference(self):
        """Tarea 13: filter_domain del campo product_tmpl_id del
        buscador — "comprobando que busca por nombre y referencia
        interna (default_code)". product.template.name_search()
        nativo NO busca default_code (verificado en el fuente); esto
        prueba la fórmula exacta que declara el arch (relativa a ESTE
        reporte, product_tmpl_id.name/.default_code) contra filas
        reales del reporte, no contra product.template suelto."""
        self.product_weight.product_tmpl_id.default_code = 'REF-TEST-13'
        day = self._far_today()
        session = self._session(day)
        claim_a = self._claim(session, self.product_weight)
        claim_b = self._claim(session, self.product_unit)
        now = fields.Datetime.now()
        self._interval(
            claim_a, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=10), end_dt=now, duration_s=10,
            kg_done=1.0, lines_done=1,
        )
        self._interval(
            claim_b, 'working', self.operator_a,
            start_dt=now - timedelta(seconds=10), end_dt=now, duration_s=10,
            kg_done=1.0, lines_done=1,
        )

        def search_by(term):
            return self.Report.sudo().search([
                ('wizard_id', '=', session.id),
                '|',
                ('product_tmpl_id.name', 'ilike', term),
                ('product_tmpl_id.default_code', 'ilike', term),
            ])

        by_name = search_by(self.product_weight.product_tmpl_id.name)
        self.assertTrue(by_name)
        self.assertTrue(all(
            r.product_tmpl_id == self.product_weight.product_tmpl_id
            for r in by_name
        ))

        by_ref = search_by('REF-TEST-13')
        self.assertTrue(by_ref)
        self.assertTrue(all(
            r.product_tmpl_id == self.product_weight.product_tmpl_id
            for r in by_ref
        ))

    def test_list_view_shows_kg_lines_ratios_by_default(self):
        """Tarea 14: "lista con Producto, Tiempo trabajado, Kg, Líneas,
        Seg/kg visibles" — la vista lista es compartida con el Reporte
        3, así que esto se logra con optional="show" (visible por
        defecto, igual se puede ocultar) en vez de optional="hide"."""
        import xml.etree.ElementTree as ET

        view = self.env.ref(
            'ist_preparation_day_picking.view_preparation_interval_report_list'
        )
        root = ET.fromstring(view.arch)
        for name in ('kg_done', 'lines_done', 'time_per_kg_s', 'time_per_box_s'):
            field = root.find(f".//field[@name='{name}']")
            self.assertEqual(
                field.get('optional'), 'show',
                f'{name}: debe ser optional="show" (visible por defecto).',
            )
