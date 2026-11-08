# -*- coding: utf-8 -*-
"""Tablet + move cancelado en Inventario (Tech Lead, 2026-11-07).

Producción 2026-11-06/07: 20 avisos del núcleo «No puede cambiar un
movimiento de existencias cancelado…» al cerrar en 0 desde la tablet una
línea cuyo PICK Inventario ya canceló. Aquí se prueba el camino REAL de
la tablet: POST call_kw guapante.preparation.day.line/write con
guapante_picking_flow y un operario con PIN (los dos `request` del write:
el de Picking y el del módulo base)."""
from unittest.mock import patch

from odoo.api import call_kw
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_preparation_day_product_claim import TestPreparationDayProductClaim

LINE_REQUEST_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_line.request'
)
PARENT_REQUEST_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day.models.preparation_day.request'
)


@tagged('post_install', '-at_install')
class TestPreparationPickingCancelledMove(TestPreparationDayProductClaim):

    def _cancelled_move_line(self):
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = session.line_ids.filtered(lambda l: l.sale_order_id == order)
        pick = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal'
            and p.state not in ('done', 'cancel')
        )
        pick.action_cancel()
        self.assertEqual(line.stock_move_id.state, 'cancel')
        return session, line

    def _write_kg_as_tablet(self, line, kg):
        mock_request = self._request_as(self.operator_a)
        with patch(LINE_REQUEST_PATCH_TARGET, mock_request), \
                patch(PARENT_REQUEST_PATCH_TARGET, mock_request):
            return call_kw(
                self.env['guapante.preparation.day.line'], 'write',
                [[line.id], {'actual_kg': kg}],
                {'context': {'guapante_picking_flow': True}},
            )

    def test_call_kw_write_zero_closes_line_on_cancelled_move(self):
        session, line = self._cancelled_move_line()
        self._write_kg_as_tablet(line, 0)
        self.assertTrue(line.is_done)
        self.assertEqual(line.actual_kg, 0.0)
        self.assertEqual(line.done_by_employee_id, self.operator_a)
        self.assertEqual(line.stock_move_id.state, 'cancel')
        self.assertEqual(line.stock_move_id.quantity, 0.0)

    def test_call_kw_write_positive_on_cancelled_move_raises_clear_error(self):
        session, line = self._cancelled_move_line()
        with self.assertRaises(UserError) as cm:
            self._write_kg_as_tablet(line, 1.5)
        self.assertIn('cancelado en Inventario', str(cm.exception))
        self.assertNotIn('existencias cancelado', str(cm.exception))
        self.assertFalse(line.is_done)

    def test_call_kw_write_normal_move_still_writes_stock(self):
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        line = session.line_ids[:1]
        self._write_kg_as_tablet(line, 1.8)
        self.assertTrue(line.is_done)
        self.assertAlmostEqual(line.stock_move_id.quantity, 1.8, places=2)
