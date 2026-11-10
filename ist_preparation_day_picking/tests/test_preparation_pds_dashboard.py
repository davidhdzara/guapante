# -*- coding: utf-8 -*-
"""PDS Operación — rediseño (F1, servidor): KPIs, ranking por operario y
ritmo del día. Se llaman por call_kw con la caché invalidada, como una
petición real de alguien con SOLO «Reportes y PDS»."""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.api import call_kw
from odoo.tests.common import tagged

from .test_preparation_day_product_claim import REQUEST_PATCH_TARGET
from .test_preparation_pds_operacion import TestPreparationPdsOperacion


@tagged('post_install', '-at_install')
class TestPreparationPdsDashboard(TestPreparationPdsOperacion):

    def _board(self):
        self.env.invalidate_all()
        Model = self.env['guapante.preparation.day'].with_user(
            self.prep_admin_user)
        with patch('odoo.fields.Datetime.now',
                   return_value=self._now_before_switch_hour()):
            data = call_kw(Model, 'get_pds_operacion_board_data', [], {})
        json.dumps(data)
        return data

    def _session_three_lines(self):
        self._create_confirmed_order(qty=2.0)
        self._create_confirmed_order(qty=3.0)
        session = self._load_session_with_product(qty=4.0)
        lines = session.line_ids
        self.assertEqual(len(lines), 3)
        return session, lines

    def _close(self, line, employee, kg):
        line.sudo().with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': kg,
            'done_by_employee_id': employee.id,
            'done_date': fields.Datetime.now(),
        })

    def _interval(self, session, claim, employee, seconds, lines, kg, open_=False):
        # Mismo reloj que _board() (parcheado): un intervalo abierto dura
        # «seconds» al leer el tablero, no los días que separan el reloj real
        # de la fecha de entrega del fixture.
        now = self._now_before_switch_hour()
        vals = {
            'wizard_id': session.id, 'claim_id': claim.id,
            'employee_id': employee.id, 'kind': 'working',
            'start_dt': now - timedelta(seconds=seconds),
            'last_touched_dt': now,
            'lines_done': lines, 'kg_done': kg,
        }
        if not open_:
            vals.update({'end_dt': now, 'duration_s': seconds})
        return self.env['guapante.preparation.interval'].sudo().create(vals)

    def test_payload_exposes_session_state(self):
        session, _lines = self._session_three_lines()
        self.assertEqual(self._board()['session_state'], session.state)

    # ── KPIs ──

    def test_kpis_match_session_counts(self):
        session, lines = self._session_three_lines()
        kpis = self._board()['kpis']
        self.assertEqual(kpis['boxes'], session.so_count)
        self.assertEqual(kpis['distinct_products'], 1)
        self.assertEqual(kpis['not_started'], 1)
        self.assertEqual(kpis['draft_count'], session.draft_count)
        self.assertEqual(kpis['boxes_match'], kpis['boxes'] == kpis['pickings'])
        self.assertGreaterEqual(kpis['pickings'], 1)

    def test_kpis_not_started_drops_when_claim_starts(self):
        session, _lines = self._session_three_lines()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        kpis = self._board()['kpis']
        self.assertEqual(kpis['not_started'], 0)
        self.assertEqual(kpis['distinct_products'], 1)

    # ── ranking ──

    def test_ranking_orders_by_lines_and_groups_by_employee(self):
        session, (l1, l2, l3) = self._session_three_lines()
        first, second, third = l1, l2, l3
        self._close(first, self.operator_b, 2.0)
        self._close(second, self.operator_a, 3.0)
        self._close(third, self.operator_a, 1.0)
        ranking = self._board()['ranking']
        self.assertEqual(
            [(r['name'], r['lines'], r['rank']) for r in ranking],
            [(self.operator_a.name, 2, 1), (self.operator_b.name, 1, 2)])
        self.assertTrue(all(r['employee_id'] for r in ranking))

    def test_zero_lines_count_as_attended_but_are_shown_apart(self):
        session, (l1, l2, _l3) = self._session_three_lines()
        self._close(l1, self.operator_a, 0.0)
        self._close(l2, self.operator_a, 2.0)
        row = self._board()['ranking'][0]
        self.assertEqual((row['lines'], row['zero_lines']), (2, 1))

    def test_ranking_uses_working_intervals_for_time_and_rate(self):
        session, (l1, l2, l3) = self._session_three_lines()
        claim = session.product_claim_ids
        self._close(l1, self.operator_a, 3.0)
        self._close(l2, self.operator_a, 3.0)
        self._close(l3, self.operator_b, 1.0)
        # A: 300 s, 2 líneas, 6 kg → 150 s/línea y 1.2 kg/min
        self._interval(session, claim, self.operator_a, 300, 2, 6.0)
        # un intervalo 'stopped' no cuenta
        self.env['guapante.preparation.interval'].sudo().create({
            'wizard_id': session.id, 'claim_id': claim.id,
            'employee_id': self.operator_a.id, 'kind': 'stopped',
            'start_dt': fields.Datetime.now() - timedelta(hours=1),
            'end_dt': fields.Datetime.now(), 'duration_s': 3600,
            'last_touched_dt': fields.Datetime.now(), 'lines_done': 9, 'kg_done': 99.0,
        })
        ranking = {r['name']: r for r in self._board()['ranking']}
        a = ranking[self.operator_a.name]
        self.assertEqual(a['avg_line_s'], 150)
        self.assertAlmostEqual(a['kg_per_min'], 1.2)
        b = ranking[self.operator_b.name]
        self.assertIsNone(b['avg_line_s'], 'sin intervalos: nunca se inventa')
        self.assertIsNone(b['kg_per_min'])

    def test_ranking_tie_broken_by_faster_average(self):
        session, (l1, l2, _l3) = self._session_three_lines()
        claim = session.product_claim_ids
        self._close(l1, self.operator_a, 1.0)
        self._close(l2, self.operator_b, 1.0)
        self._interval(session, claim, self.operator_a, 600, 1, 1.0)
        self._interval(session, claim, self.operator_b, 120, 1, 1.0)
        names = [r['name'] for r in self._board()['ranking']]
        self.assertEqual(names, [self.operator_b.name, self.operator_a.name])

    def test_ranking_products_listed(self):
        session, (l1, _l2, _l3) = self._session_three_lines()
        self._close(l1, self.operator_a, 1.0)
        row = self._board()['ranking'][0]
        self.assertEqual(row['products'], [self.product_weight.product_tmpl_id.name])

    def test_empty_ranking_and_rhythm_without_closed_lines(self):
        self._session_three_lines()
        data = self._board()
        self.assertEqual(data['ranking'], [])
        self.assertIsNone(data['rhythm']['best'])
        self.assertIsNone(data['rhythm']['avg_kg_per_min'])
        self.assertEqual(data['rhythm']['active_operators'], 0)

    # ── ritmo ──

    def test_rhythm_active_operators_and_best(self):
        session, (l1, l2, l3) = self._session_three_lines()
        claim = session.product_claim_ids
        self._close(l1, self.operator_a, 3.0)
        self._close(l2, self.operator_a, 3.0)
        self._close(l3, self.operator_b, 1.0)
        self._interval(session, claim, self.operator_a, 300, 2, 6.0)
        # B está trabajando ahora (intervalo abierto)
        self._interval(session, claim, self.operator_b, 60, 0, 0.0, open_=True)
        rhythm = self._board()['rhythm']
        self.assertEqual(rhythm['active_operators'], 1)
        self.assertEqual(rhythm['best']['name'], self.operator_a.name)
        self.assertEqual(rhythm['best']['lines'], 2)
        # el único activo con dato de kg/min es nadie (B sin kg) → sin promedio
        self.assertIsNone(rhythm['avg_kg_per_min'])

    def test_rhythm_average_over_active_operators_with_rate(self):
        session, (l1, l2, _l3) = self._session_three_lines()
        claim = session.product_claim_ids
        self._close(l1, self.operator_a, 3.0)
        self._close(l2, self.operator_b, 2.0)
        self._interval(session, claim, self.operator_a, 300, 1, 6.0, open_=True)
        self._interval(session, claim, self.operator_b, 300, 1, 3.0, open_=True)
        rhythm = self._board()['rhythm']
        self.assertEqual(rhythm['active_operators'], 2)
        # A ≈ 6/5 = 1.2 y B ≈ 3/5 = 0.6 kg/min → promedio ≈ 0.9
        self.assertAlmostEqual(rhythm['avg_kg_per_min'], 0.9, delta=0.05)
