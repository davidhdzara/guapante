# -*- coding: utf-8 -*-
"""Lote 3 (David, 2026-11-09), parte de Picking: al cancelarse un pedido
sus líneas pendientes salen de la sesión (ist_preparation_day) y el
producto desaparece del Nivel 1 si se quedó sin ninguna línea; si le
quedan líneas de otros pedidos, el claim se conserva."""
from unittest.mock import patch

from odoo.api import call_kw
from odoo.tests.common import tagged

from .test_preparation_day_product_claim import (
    REQUEST_PATCH_TARGET,
    TestPreparationDayProductClaim,
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
