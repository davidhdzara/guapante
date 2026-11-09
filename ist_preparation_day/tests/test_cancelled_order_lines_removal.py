# -*- coding: utf-8 -*-
"""Lote 3 (David, 2026-11-09): al cancelar un pedido, sus líneas
PENDIENTES desaparecen de Preparación (y, por el gancho de
ist_preparation_day_picking, del Picking) sin pulsar «Cargar». Ventas e
Inventario quedan en «Cancelado»; las cajas no se renumeran.

Antecedente real: pedido S15615 (producción, 2026-11-08) — 33 líneas
seguían en la sesión 229 y en el Picking con el pedido cancelado."""
from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _date_to_utc_range,
)

from .test_preparation_day import TestPreparationDay

REMOVE_IN_SESSION = (
    'odoo.addons.ist_preparation_day.models.preparation_day'
    '.PreparationDay._guapante_remove_cancelled_lines_in_session'
)


@tagged('post_install', '-at_install')
class TestCancelledOrderLinesRemoval(TestPreparationDay):

    def _two_orders_loaded(self):
        """Dos pedidos del mismo producto en la misma sesión cargada."""
        order_a = self._create_confirmed_order(qty=3.0)
        order_b = self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        Line = self.env['guapante.preparation.day.line'].sudo()
        line_a = Line.search([('sale_order_id', '=', order_a.id)])
        line_b = Line.search([('sale_order_id', '=', order_b.id)])
        self.assertTrue(line_a and line_b)
        return session, order_a, order_b, line_a, line_b

    def _summary(self, session, line):
        return session.summary_ids.filtered(
            lambda s: s.product_id == line.product_product_id
        )

    def _notes(self, session):
        return ' '.join(session.message_ids.mapped('body'))

    def _assert_sales_and_stock_untouched_but_cancelled(self, order, move):
        self.assertEqual(order.state, 'cancel')
        self.assertTrue(move.exists(), 'el traslado no se borra')
        self.assertEqual(move.state, 'cancel')
        self.assertEqual(move.picking_id.state, 'cancel')

    # ── Los tres caminos de cancelación terminan en _action_cancel ──

    def test_action_cancel_method_removes_pending_lines(self):
        session, order_a, order_b, line_a, line_b = self._two_orders_loaded()
        seq_b = line_b.daily_sequence
        move_a = line_a.stock_move_id
        summary = self._summary(session, line_a)
        self.assertEqual(summary.order_count, 2)
        est_before = summary.total_estimated_kg

        order_a._action_cancel()

        self.assertFalse(line_a.exists(), 'la línea del pedido cancelado desaparece')
        self.assertTrue(line_b.exists(), 'la del otro pedido se queda')
        self.assertEqual(line_b.daily_sequence, seq_b, 'las cajas no se renumeran')
        self.assertEqual(summary.order_count, 1)
        self.assertLess(summary.total_estimated_kg, est_before)
        self._assert_sales_and_stock_untouched_but_cancelled(order_a, move_a)
        self.assertIn(f'Pedido {order_a.name} cancelado', self._notes(session))

    def test_native_cancel_wizard_removes_pending_lines(self):
        session, order_a, _order_b, line_a, _line_b = self._two_orders_loaded()
        move_a = line_a.stock_move_id
        wizard = self.env['sale.order.cancel'].create({'order_id': order_a.id})
        wizard.action_cancel()
        self.assertFalse(line_a.exists())
        self._assert_sales_and_stock_untouched_but_cancelled(order_a, move_a)

    def test_action_cancel_button_with_warning_disabled(self):
        session, order_a, _order_b, line_a, _line_b = self._two_orders_loaded()
        order_a.with_context(disable_cancel_warning=True).action_cancel()
        self.assertFalse(line_a.exists())

    # ── Casos que NO se borran ──

    def test_done_line_is_kept_with_a_note(self):
        session, order_a, _order_b, line_a, _line_b = self._two_orders_loaded()
        line_a.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 1.0,
        })
        order_a._action_cancel()
        self.assertTrue(line_a.exists(), 'una línea ya terminada no se toca')
        self.assertIn('se conservan', self._notes(session))

    def test_closed_session_is_not_touched_only_a_note(self):
        session, order_a, _order_b, line_a, _line_b = self._two_orders_loaded()
        session.write({'state': 'done'})
        order_a._action_cancel()
        self.assertTrue(line_a.exists())
        self.assertIn('ya está cerrada', self._notes(session))

    # ── Robustez ──

    def test_is_idempotent(self):
        session, order_a, _order_b, line_a, _line_b = self._two_orders_loaded()
        order_a._action_cancel()
        notes_after_first = len(session.message_ids)
        self.env['guapante.preparation.day']._guapante_remove_cancelled_order_lines(
            order_a,
        )
        self.assertEqual(len(session.message_ids), notes_after_first)
        self.assertFalse(line_a.exists())

    def test_internal_failure_never_blocks_the_cancellation(self):
        session, order_a, _order_b, line_a, _line_b = self._two_orders_loaded()
        with patch(REMOVE_IN_SESSION, side_effect=RuntimeError('boom')):
            order_a._action_cancel()
        self.assertEqual(order_a.state, 'cancel')
        self.assertTrue(line_a.exists(), 'si falla, la línea queda (el barrido la retira)')

    def test_only_cancelled_orders_are_processed(self):
        session, order_a, order_b, line_a, line_b = self._two_orders_loaded()
        self.env['guapante.preparation.day']._guapante_remove_cancelled_order_lines(
            order_a | order_b,
        )  # ninguno cancelado todavía
        self.assertTrue(line_a.exists() and line_b.exists())

    # ── Reconfirmar: caja nueva MAX+1, nunca la anterior ──

    def test_reconfirmed_order_enters_with_a_new_box_max_plus_one(self):
        session, order_a, order_b, line_a, line_b = self._two_orders_loaded()
        seq_a, seq_b = line_a.daily_sequence, line_b.daily_sequence
        order_a._action_cancel()
        order_a.action_draft()
        order_a.action_confirm()
        dt_start, _dt_end = _date_to_utc_range(self.env, self.delivery_date)
        for picking in order_a.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        ):
            picking.scheduled_date = dt_start
        session.action_load()
        new_line = self.env['guapante.preparation.day.line'].sudo().search([
            ('sale_order_id', '=', order_a.id), ('wizard_id', '=', session.id),
        ])
        self.assertTrue(new_line, 'el pedido reconfirmado vuelve a la sesión')
        self.assertEqual(
            new_line.daily_sequence, seq_b + 1,
            'regla de David: el pedido que entra de nuevo toma MAX+1 de la '
            'sesión, no la caja que tenía (que quedó como hueco)',
        )
        self.assertEqual(line_b.daily_sequence, seq_b, 'las demás no se mueven')
        self.assertNotEqual(new_line.daily_sequence, seq_a)
