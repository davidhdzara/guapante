# -*- coding: utf-8 -*-
"""Desechar (punto 5, 2026-11-10): contador de desechos por producto/sesión,
el administrador también puede desechar y Desechar NO toca líneas ni el
estado del claim."""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_preparation_day_picking_fase_d import (
    REQUEST_PATCH_TARGET_CLAIM,
    REQUEST_PATCH_TARGET_SCRAP,
    TestPreparationDayPickingFaseD,
)


@tagged('post_install', '-at_install')
class TestPreparationScrapVisibility(TestPreparationDayPickingFaseD):

    def _scrap(self, session, claim, qty, product=None):
        return self.env['stock.scrap'].with_context(
            guapante_picking_flow=True,
            picking_wizard_id=session.id,
            picking_claim_id=claim.id,
        ).create({
            'product_id': (product or self.product_weight).id,
            'scrap_qty': qty,
        })

    def _do(self, scrap, employee):
        with patch(REQUEST_PATCH_TARGET_SCRAP, self._request_as(employee)):
            scrap.do_scrap()

    def _make_admin(self):
        self.env.user.sudo().write({'groups_id': [(4, self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin').id)]})

    def test_counter_sums_only_done_scraps_of_this_session_and_template(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        self.assertEqual((claim.scrap_count, claim.scrap_qty), (0, 0))
        self._do(self._scrap(session, claim, 1.0), self.operator_a)
        self._do(self._scrap(session, claim, 2.5), self.operator_a)
        # un desecho a medio hacer (borrador) no cuenta
        self._scrap(session, claim, 9.0)
        # un desecho de otra sesión/origen no cuenta
        other = self.env['stock.scrap'].create({
            'product_id': self.product_weight.id, 'scrap_qty': 4.0,
            'origin': 'OTRA-SESION'})
        other.do_scrap()
        claim.invalidate_recordset()
        self.assertEqual(claim.scrap_count, 2)
        self.assertAlmostEqual(claim.scrap_qty, 3.5)

    def test_scrap_does_not_touch_lines_or_claim_state(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        before = [
            (l.id, l.is_done, l.actual_kg) for l in session.line_ids]
        status, owner = claim.status, claim.assigned_employee_id
        self._do(self._scrap(session, claim, 1.0), self.operator_a)
        claim.invalidate_recordset()
        self.assertEqual(
            before,
            [(l.id, l.is_done, l.actual_kg) for l in session.line_ids])
        self.assertEqual(claim.status, status)
        self.assertEqual(claim.assigned_employee_id, owner)

    def test_non_owner_non_admin_cannot_open_scrap_wizard(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        with patch(REQUEST_PATCH_TARGET_CLAIM,
                   self._request_as(self.operator_b)):
            with self.assertRaises(UserError):
                claim.action_open_scrap_wizard()

    def test_admin_can_open_scrap_wizard_on_someone_elses_claim(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        self._make_admin()
        with patch(REQUEST_PATCH_TARGET_CLAIM,
                   self._request_as(self.operator_b)):
            action = claim.action_open_scrap_wizard()
        self.assertEqual(action['res_model'], 'stock.scrap')
        self.assertTrue(action['views'])

    def test_admin_can_scrap_on_someone_elses_claim(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        self._make_admin()
        scrap = self._scrap(session, claim, 1.5)
        self._do(scrap, self.operator_b)
        self.assertEqual(scrap.state, 'done')
        claim.invalidate_recordset()
        self.assertEqual(claim.scrap_count, 1)

    def test_admin_still_cannot_scrap_other_template(self):
        """El admin salta el dueño, no la coherencia de producto."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        self._make_admin()
        other = self.env['product.product'].create({
            'name': 'Otro producto desecho', 'type': 'consu',
            'uom_id': self.uom_kg.id, 'uom_po_id': self.uom_kg.id})
        with self.assertRaises(UserError):
            self._do(self._scrap(session, claim, 1.0, product=other),
                     self.operator_b)
