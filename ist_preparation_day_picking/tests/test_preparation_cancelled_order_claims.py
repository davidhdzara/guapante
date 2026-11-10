# -*- coding: utf-8 -*-
"""Lote 3 (David, 2026-11-09), parte de Picking: al cancelarse un pedido
sus líneas pendientes salen de la sesión (ist_preparation_day) y el
producto desaparece del Nivel 1 si se quedó sin ninguna línea; si le
quedan líneas de otros pedidos, el claim se conserva."""
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


@tagged('post_install', '-at_install')
class TestPreparationCancelledOrderClaims(TestPreparationDayProductClaim):

    def _l1_ids(self, session):
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            records = call_kw(
                self.Claim, 'get_claims_for_level1_display', [session.id], {},
            )
        return {r['id'] for r in records}

    def test_product_without_remaining_lines_disappears_from_picking(self):
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        self.assertEqual(len(claim), 1)
        self.assertIn(claim.id, self._l1_ids(session))

        order._action_cancel()

        self.assertFalse(claim.exists(), 'el claim sin líneas se borra')
        self.assertFalse(session.product_claim_ids)
        self.assertFalse(self._l1_ids(session))

    def test_claim_with_lines_of_other_orders_is_kept(self):
        order_a = self._create_confirmed_order(qty=3.0)
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        self.assertEqual(claim.total_line_count, 2)

        order_a._action_cancel()

        self.assertTrue(claim.exists())
        self.assertEqual(claim.total_line_count, 1)
        self.assertIn(claim.id, self._l1_ids(session))

    def test_taken_claim_is_removed_with_its_intervals_without_error(self):
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        self.assertEqual(claim.status, 'in_progress')

        order._action_cancel()

        self.assertFalse(claim.exists())
        self.assertFalse(self.Interval.sudo().search([
            ('claim_id', '=', claim.id),
        ]))

    def test_claim_with_a_done_line_is_never_removed(self):
        order_a = self._create_confirmed_order(qty=3.0)
        order_b = self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        Line = self.env['guapante.preparation.day.line'].sudo()
        Line.search([('sale_order_id', '=', order_b.id)]).with_context(
            skip_auto_save=True,
        ).write({'is_done': True, 'actual_kg': 1.0})

        order_a._action_cancel()

        self.assertTrue(claim.exists())
        self.assertEqual(claim.status, 'done')

    # ── Operario con la tarjeta abierta cuando la línea se retira ──

    def _retired_line_id(self):
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = self.env['guapante.preparation.day.line'].sudo().search([
            ('sale_order_id', '=', order.id),
        ])
        line_id = line.id
        order._action_cancel()
        self.assertFalse(line.exists())
        return line_id

    def test_write_on_retired_line_via_call_kw_gives_clear_message(self):
        line_id = self._retired_line_id()
        mock_request = self._request_as(self.operator_a)
        with patch(LINE_REQUEST_PATCH_TARGET, mock_request), \
                patch(PARENT_REQUEST_PATCH_TARGET, mock_request):
            with self.assertRaises(UserError) as cm:
                call_kw(
                    self.env['guapante.preparation.day.line'], 'write',
                    [[line_id], {'actual_kg': 1.5}],
                    {'context': {'guapante_picking_flow': True}},
                )
        self.assertIn('su pedido fue cancelado', str(cm.exception))
        self.assertNotIn('does not exist', str(cm.exception))

    def test_add_note_on_retired_line_via_call_kw_gives_clear_message(self):
        line_id = self._retired_line_id()
        mock_request = self._request_as(self.operator_a)
        with patch(LINE_REQUEST_PATCH_TARGET, mock_request), \
                patch(PARENT_REQUEST_PATCH_TARGET, mock_request):
            with self.assertRaises(UserError) as cm:
                call_kw(
                    self.env['guapante.preparation.day.line'],
                    'action_add_note', [[line_id], 'hola'],
                    {'context': {'guapante_picking_flow': True}},
                )
        self.assertIn('su pedido fue cancelado', str(cm.exception))

