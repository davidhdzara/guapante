# -*- coding: utf-8 -*-
"""Productos detenidos con líneas ya pesadas (punto 3, 2026-11-09):
lista de administrador de solo lectura, notas al detener/liberar solo si
hay pesadas, y corregir desde un Detenido no cambia su estado."""
from contextlib import contextmanager
from unittest.mock import patch

from odoo.api import call_kw
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .test_preparation_day_product_claim import (
    REQUEST_PATCH_TARGET,
    TestPreparationDayProductClaim,
)
from .test_preparation_js_call_kw import (
    LINE_REQUEST_PATCH_TARGET,
    PARENT_REQUEST_PATCH_TARGET,
)


@tagged('post_install', '-at_install')
class TestPreparationStoppedProducts(TestPreparationDayProductClaim):

    @contextmanager
    def _tablet(self, employee=None):
        mock_request = self._request_as(employee or self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_request), \
                patch(LINE_REQUEST_PATCH_TARGET, mock_request), \
                patch(PARENT_REQUEST_PATCH_TARGET, mock_request):
            yield

    def _session_two_lines(self):
        self._create_confirmed_order(qty=2.0)
        session = self._load_session_with_product(qty=3.0)
        self.assertEqual(len(session.line_ids), 2)
        return session, session.product_claim_ids

    def _weigh(self, line, kg):
        line.sudo().with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': kg,
            'done_by_employee_id': self.operator_a.id,
        })

    def _notes(self, session):
        return ' '.join(session.message_ids.mapped('body'))

    def _admin_user(self):
        return self.env['res.users'].create({
            'name': 'Admin prep', 'login': 'admin_prep_stopped',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref(
                    'ist_preparation_day_picking.group_preparation_admin').id,
            ])],
        })

    def _operator_user(self):
        return self.env['res.users'].create({
            'name': 'Op prep', 'login': 'op_prep_stopped',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref(
                    'ist_preparation_day_picking.'
                    'group_preparation_picking_operator').id,
            ])],
        })

    # ── conteos ──

    def test_weighed_counts_mix_of_weighed_and_pending(self):
        session, claim = self._session_two_lines()
        self.assertEqual((claim.weighed_line_count, claim.weighed_kg), (0, 0))
        self._weigh(session.line_ids[0], 2.5)
        claim.invalidate_recordset()
        self.assertEqual(claim.weighed_line_count, 1)
        self.assertAlmostEqual(claim.weighed_kg, 2.5)
        self.assertEqual(claim.total_line_count, 2)

    def test_zero_closed_line_is_not_counted_as_weighed(self):
        session, claim = self._session_two_lines()
        self._weigh(session.line_ids[0], 0.0)
        claim.invalidate_recordset()
        self.assertEqual(claim.weighed_line_count, 0)

    # ── notas ──

    def test_stop_with_weighed_lines_leaves_note(self):
        session, claim = self._session_two_lines()
        self._weigh(session.line_ids[0], 2.5)
        with self._tablet():
            claim.action_assign()
            claim.action_stop('sin_stock')
        self.assertIn('Detenido con 1 de 2 línea(s) ya pesadas (2.50 kg)',
                      self._notes(session))

    def test_stop_without_weighed_lines_leaves_no_weighed_note(self):
        session, claim = self._session_two_lines()
        with self._tablet():
            claim.action_assign()
            claim.action_stop('sin_stock')
        self.assertNotIn('ya pesadas', self._notes(session))

    def test_unstop_with_weighed_lines_leaves_note(self):
        session, claim = self._session_two_lines()
        with self._tablet():
            claim.action_assign()
            claim.action_stop('sin_stock')
            self._weigh(session.line_ids[0], 1.0)
            claim.action_unstop()
        self.assertIn('Liberado con 1 de 2 línea(s) ya pesadas',
                      self._notes(session))

    def test_unstop_without_weighed_lines_leaves_no_weighed_note(self):
        session, claim = self._session_two_lines()
        with self._tablet():
            claim.action_assign()
            claim.action_stop('sin_stock')
            claim.action_unstop()
        self.assertNotIn('ya pesadas', self._notes(session))

    # ── corregir desde un Detenido ──

    def test_correcting_a_weighed_line_keeps_the_product_stopped(self):
        session, claim = self._session_two_lines()
        line = session.line_ids[0]
        self._weigh(line, 2.5)
        with self._tablet():
            claim.action_assign()
            claim.action_stop('sin_stock')
            self.assertEqual(claim.status, 'stopped')
            line.action_undo_line()
        claim.invalidate_recordset()
        self.assertEqual(claim.status, 'stopped')
        self.assertFalse(line.is_done)
        self.assertIn('la devolvió a Pendiente', self._notes(session))

    # ── acceso ──

    def test_open_lines_returns_valid_action_for_admin_via_call_kw(self):
        session, claim = self._session_two_lines()
        admin = self._admin_user()
        action = call_kw(
            self.Claim.with_user(admin), 'action_open_lines_admin',
            [[claim.id]], {})
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertTrue(action['views'])
        self.assertEqual(action['res_model'], 'guapante.preparation.day.line')
        lines = self.env['guapante.preparation.day.line'].search(
            action['domain'])
        self.assertEqual(lines, session.line_ids)

    def test_open_lines_rejected_for_plain_picking_operator(self):
        _session, claim = self._session_two_lines()
        op = self._operator_user()
        with self.assertRaises(AccessError):
            call_kw(self.Claim.with_user(op), 'action_open_lines_admin',
                    [[claim.id]], {})

    def test_menu_visible_only_to_admin_groups(self):
        menu = self.env.ref(
            'ist_preparation_day_picking.menu_claim_stopped')
        admin = self._admin_user()
        op = self._operator_user()
        self.assertIn(menu, self.env['ir.ui.menu'].with_user(admin)
                      .search([('id', '=', menu.id)]))
        self.assertNotIn(menu, self.env['ir.ui.menu'].with_user(op)
                         .search([('id', '=', menu.id)]))

    def test_list_is_read_only_and_filters_stopped(self):
        action = self.env.ref(
            'ist_preparation_day_picking.action_claim_stopped')
        self.assertIn('stopped', action.domain)
        view = self.env.ref(
            'ist_preparation_day_picking.view_claim_stopped_list')
        for attr in ('create="0"', 'edit="0"', 'delete="0"'):
            self.assertIn(attr, view.arch_db)
