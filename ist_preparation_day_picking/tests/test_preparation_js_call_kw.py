# -*- coding: utf-8 -*-
"""Contrato RPC de los métodos que el JS de Picking invoca con orm.call
(Tech Lead, 2026-11-08/09 — revisión completa pedida por David tras el
IndexError del PDS).

El JS llama `orm.call(modelo, método, args, kwargs)` y el servidor lo
atiende con odoo.api.call_kw: un método de instancia sin ids revienta
con IndexError, un método @api.model con ids se rompe, y un
ir.actions.act_window devuelto SIN `views` revienta en el cliente
(_preprocessAction hace action.views.map) porque orm.call no pasa por
clean_action. Llamar al método directo desde Python NO detecta nada de
eso — por eso cada test pasa por call_kw con la misma forma de
argumentos que usa el JS (ver los orm.call de static/src/js/).

Cubiertos acá (modelo.método → archivo JS):
  guapante.preparation.day.action_resolve_picking_handoff  (app.js, level1)
  ...product.claim.get_claims_for_level1_display            (level1)
  ...product.claim.action_assign / action_resume / action_release /
     action_unstop / action_open_lines_kanban /
     action_open_stop_wizard / action_open_scrap_wizard     (level1 _callClaim)
  ...product.claim.get_my_open_interval                     (visit_timer)
  guapante.preparation.day.line.action_add_note             (level2)
Ya cubiertos en otros archivos: get_pds_operacion_board_data
(test_preparation_pds_operacion) y guapante.preparation.day.line/write con
guapante_picking_flow (test_preparation_picking_cancelled_move).
"""
import json
from contextlib import contextmanager
from unittest.mock import patch

from odoo.api import call_kw
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_preparation_day_product_claim import (
    REQUEST_PATCH_TARGET,
    TestPreparationDayProductClaim,
)

LINE_REQUEST_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_line.request'
)
PARENT_REQUEST_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day.models.preparation_day.request'
)

CLAIM = 'guapante.preparation.day.product.claim'


@tagged('post_install', '-at_install')
class TestPreparationJsCallKw(TestPreparationDayProductClaim):

    # ── helpers ──

    @contextmanager
    def _tablet(self, employee=None):
        """Operario identificado con PIN en los tres módulos que leen
        `request` (claim, línea y modelo base)."""
        mock_request = self._request_as(employee or self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_request), \
                patch(LINE_REQUEST_PATCH_TARGET, mock_request), \
                patch(PARENT_REQUEST_PATCH_TARGET, mock_request):
            yield

    def _claim(self):
        return self._load_session_with_product().product_claim_ids

    def _kw(self, claim, method, args=None, kwargs=None):
        """Misma forma que `_callClaim` del level1: [[claimId], ...args]."""
        return call_kw(self.Claim, method, [[claim.id]] + list(args or []),
                       kwargs or {})

    def _assert_valid_action(self, action):
        """Lo que el cliente necesita de una acción devuelta por orm.call."""
        self.assertIsInstance(action, dict)
        json.dumps(action)  # tiene que viajar por JSON-RPC
        if action['type'] == 'ir.actions.act_window':
            self.assertTrue(
                action.get('views'),
                'act_window sin `views`: _preprocessAction del cliente '
                'revienta (orm.call no pasa por clean_action)',
            )
            for view in action['views']:
                self.assertEqual(len(view), 2)
                self.assertTrue(view[1])
        elif action['type'] == 'ir.actions.client':
            self.assertTrue(action.get('tag'))
        else:
            self.fail(f"tipo de acción inesperado: {action['type']}")

    # ── guapante.preparation.day ──

    def test_action_resolve_picking_handoff_with_empty_args(self):
        """level1: orm.call(day, 'action_resolve_picking_handoff', [], {})
        y app.js: ..., [], {context: ...} — sin ids (@api.model)."""
        Day = self.env['guapante.preparation.day']
        for kwargs in ({}, {'context': {}}):
            action = call_kw(Day, 'action_resolve_picking_handoff', [], kwargs)
            self._assert_valid_action(action)
            self.assertEqual(action['tag'], 'guapante_picking_level1')

    def test_action_resolve_picking_handoff_respects_session_in_context(self):
        session = self._load_session_with_product()
        action = call_kw(
            self.env['guapante.preparation.day'],
            'action_resolve_picking_handoff', [],
            {'context': {'picking_session_id': session.id}},
        )
        self._assert_valid_action(action)
        self.assertEqual(action['context'].get('wizard_id'), session.id)

    # ── claim: lectura de Nivel 1 ──

    def test_get_claims_for_level1_display_via_call_kw(self):
        """level1: orm.call(claim, 'get_claims_for_level1_display',
        [wizardId]) — @api.model, el id de sesión va como arg posicional."""
        session = self._load_session_with_product()
        with self._tablet():
            records = call_kw(self.Claim, 'get_claims_for_level1_display',
                              [session.id], {})
        self.assertEqual(len(records), 1)
        for key in (
            'id', 'status', 'touched_by_me', 'customer_names_summary',
            'done_by_employee_name', 'done_time_label',
            'time_working_s', 'time_stopped_s',
            'time_working_open_count', 'time_stopped_open_count',
        ):
            self.assertIn(key, records[0], f'el JS lee `{key}`')

    # ── claim: acciones de Nivel 1 (_callClaim) ──

    def test_action_assign_via_call_kw_returns_level2_client_action(self):
        claim = self._claim()
        with self._tablet():
            action = self._kw(claim, 'action_assign')
        self._assert_valid_action(action)
        self.assertEqual(action['tag'], 'guapante_picking_level2')
        self.assertEqual(claim.status, 'in_progress')

    def test_action_open_lines_kanban_via_call_kw(self):
        claim = self._claim()
        with self._tablet():
            self._kw(claim, 'action_assign')
            action = self._kw(claim, 'action_open_lines_kanban')
        self._assert_valid_action(action)
        self.assertEqual(action['tag'], 'guapante_picking_level2')
        self.assertTrue(action['context'].get('guapante_picking_flow'))
        self.assertEqual(action['context'].get('claim_id'), claim.id)

    def test_action_release_via_call_kw(self):
        claim = self._claim()
        with self._tablet():
            self._kw(claim, 'action_assign')
            result = self._kw(claim, 'action_release')
        self.assertIs(result, True)
        self.assertEqual(claim.status, 'pending')

    def test_action_resume_via_call_kw(self):
        claim = self._claim()
        with self._tablet():
            self._kw(claim, 'action_assign')
            claim.action_stop('sin_stock')
            self.assertEqual(claim.status, 'stopped')
            action = self._kw(claim, 'action_resume')
        self._assert_valid_action(action)
        self.assertEqual(claim.status, 'in_progress')

    def test_action_unstop_via_call_kw(self):
        claim = self._claim()
        with self._tablet():
            self._kw(claim, 'action_assign')
            claim.action_stop('sin_stock')
            result = self._kw(claim, 'action_unstop')
        self.assertIs(result, True)
        self.assertNotEqual(claim.status, 'stopped')

    def test_action_open_stop_wizard_via_call_kw_has_views(self):
        """Prioridad (Tech Lead): devuelve un act_window al cliente sin
        pasar por clean_action — sin `views` el cliente no abre el
        diálogo de «¿Por qué se detiene?»."""
        claim = self._claim()
        with self._tablet():
            self._kw(claim, 'action_assign')
            action = self._kw(claim, 'action_open_stop_wizard')
        self._assert_valid_action(action)
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], f'{CLAIM}.stop.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['views'], [(False, 'form')])
        self.assertEqual(action['context'].get('default_claim_id'), claim.id)

    def test_action_open_scrap_wizard_via_call_kw_has_views(self):
        """Prioridad (Tech Lead): abre el diálogo nativo de stock.scrap
        con el contexto de Picking; solo el dueño del claim."""
        claim = self._claim()
        scrap_view = self.env.ref('stock.stock_scrap_form_view2')
        with self._tablet():
            self._kw(claim, 'action_assign')
            action = self._kw(claim, 'action_open_scrap_wizard')
        self._assert_valid_action(action)
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'stock.scrap')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['views'], [(scrap_view.id, 'form')])
        self.assertTrue(action['context'].get('guapante_picking_flow'))
        self.assertEqual(action['context'].get('picking_claim_id'), claim.id)
        self.assertEqual(
            action['context'].get('picking_wizard_id'), claim.wizard_id.id,
        )

    def test_action_open_scrap_wizard_rejects_non_owner(self):
        claim = self._claim()
        with self._tablet(self.operator_a):
            self._kw(claim, 'action_assign')
        with self._tablet(self.operator_b):
            with self.assertRaises(UserError) as cm:
                self._kw(claim, 'action_open_scrap_wizard')
        self.assertIn('no está asignado a ti', str(cm.exception))

    # ── claim: cronómetro de Nivel 2 ──

    def test_get_my_open_interval_via_call_kw(self):
        """visit_timer.js: orm.call(claim, 'get_my_open_interval',
        [[claimId]]) — el JS lee start_dt / server_now / accumulated_s."""
        claim = self._claim()
        with self._tablet():
            self._kw(claim, 'action_assign')
            result = self._kw(claim, 'get_my_open_interval')
        self.assertEqual(
            set(result), {'start_dt', 'server_now', 'accumulated_s'},
        )
        self.assertTrue(result['start_dt'], 'Asignarme abre el intervalo')
        self.assertTrue(result['server_now'])
        self.assertEqual(result['accumulated_s'], 0)

    # ── línea: notas de Nivel 2 ──

    def test_action_add_note_via_call_kw(self):
        """level2: orm.call(line, 'action_add_note', [[line.id], text],
        {context: {guapante_picking_flow: true}})."""
        session = self._load_session_with_product()
        line = session.line_ids[:1]
        with self._tablet():
            result = call_kw(
                self.env['guapante.preparation.day.line'], 'action_add_note',
                [[line.id], 'nota desde la tablet'],
                {'context': {'guapante_picking_flow': True}},
            )
        self.assertTrue(result)
        self.assertTrue(any(
            'nota desde la tablet' in (body or '')
            for body in session.message_ids.mapped('body')
        ))
