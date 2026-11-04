# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
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
        today = fields.Date.context_today(self.env["sale.order"])
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
        today = fields.Date.context_today(self.env["sale.order"])
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
        today = fields.Date.context_today(self.env["sale.order"])
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
        today = fields.Date.context_today(self.env["sale.order"])
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
        today = fields.Date.context_today(self.env["sale.order"])
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
        today = fields.Date.context_today(self.env["sale.order"])
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
        today = fields.Date.context_today(self.env["sale.order"])
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
        day1 = fields.Date.context_today(self.env["sale.order"])
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
