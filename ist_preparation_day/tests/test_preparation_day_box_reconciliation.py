# -*- coding: utf-8 -*-
"""Corrección #5/#6, David/Tech Lead 2026-10-31: "Cajas" (so_count) se
calculaba buscando stock.picking por fecha programada — podía mostrar
un número distinto al real de la sesión (ej. 10 vs 8 reportado por
David). Con líneas ya cargadas, son la fuente de verdad: distinct
sale_order_id de line_ids, sin filtrar por estado del pedido (un
cancelado que conserva su número sigue contando mientras sus líneas
sigan en la sesión). box_diff/box_match NO dependen de so_count — se
mantienen fijos en 0/True antes y después de esta corrección.
"""
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _date_to_utc_range,
)
from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)


@tagged('post_install', '-at_install')
class TestPreparationDayBoxReconciliation(TestPreparationDay):

    def _create_stray_done_picking(self):
        """Simula un pedido/picking del proceso viejo en
        self.delivery_date, pero SIN línea de Preparación — a
        propósito NO usa action_confirm() (dispara
        _guapante_add_confirmed_order, que sí sincroniza) ni reprograma
        un picking real (dispara _guapante_relocate_picking, que
        también sincroniza). El filtro viejo (_compute_box_reconciliation,
        rama sin líneas) solo exige state != 'cancel' — ni siquiera
        pide 'done' — así que un picking recién creado (nace en
        'draft', state es compute sin inverse real desde moves) ya
        reproduce la situación real que reportó David: un picking que
        el cálculo viejo por fecha sigue contando pero que la sesión
        nunca cargó."""
        dt_start, _dt_end = _date_to_utc_range(self.env, self.delivery_date)
        order = self.env['sale.order'].create({
            'partner_id': self.child_partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product_weight.id,
                'product_uom_qty': 1.0,
            })],
        })
        order.write({'state': 'sale'})
        PickType = self.warehouse.pick_type_id
        self.env['stock.picking'].create({
            'picking_type_id': PickType.id,
            'location_id': PickType.default_location_src_id.id,
            'location_dest_id': PickType.default_location_dest_id.id,
            'partner_id': self.child_partner.id,
            'sale_id': order.id,
            'scheduled_date': dt_start,
        })
        return order

    def test_so_count_counts_distinct_orders_from_lines(self):
        self._create_confirmed_order(qty=2.0)
        self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        self.assertEqual(len(session.line_ids.mapped('sale_order_id')), 2)
        self.assertEqual(session.so_count, 2)

    def test_so_count_david_scenario_8_orders_plus_2_done_pickings_elsewhere(self):
        """Caso real reportado por David: 8 pedidos con líneas en la
        sesión, más 2 pickings 'done' de OTROS pedidos el mismo día
        (proceso viejo, nunca cargados) — debe dar 8, no 10."""
        for _ in range(8):
            self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        self.assertEqual(len(session.line_ids.mapped('sale_order_id')), 8)

        for _ in range(2):
            self._create_stray_done_picking()

        session.invalidate_recordset(['so_count'])
        self.assertEqual(
            session.so_count, 8,
            'los 2 pickings done de pedidos que NUNCA se cargaron a la '
            'sesión no deben inflar el conteo',
        )

    def test_so_count_ignores_lines_without_sale_order_id(self):
        session = self._create_session()
        self._create_confirmed_order(qty=2.0)
        session.action_load()
        self.assertEqual(session.so_count, 1)

        self.env['guapante.preparation.day.line'].create({
            'wizard_id': session.id,
            'product_product_id': self.product_weight.id,
            'order_name': 'Línea manual sin pedido',
            'estimated_kg': 1.0,
        })
        session.invalidate_recordset(['so_count'])
        self.assertEqual(
            session.so_count, 1,
            'una línea sin sale_order_id no debe contar como una caja más',
        )

    def test_so_count_counts_cancelled_order_while_its_lines_remain(self):
        order = self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        self.assertEqual(session.so_count, 1)

        order.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        ).action_cancel()
        order.action_cancel()
        session.invalidate_recordset(['so_count'])
        self.assertEqual(
            session.so_count, 1,
            'un pedido cancelado que conserva su número sigue contando '
            'mientras sus líneas sigan en la sesión',
        )

    def test_so_count_excludes_cancelled_order_once_its_lines_are_deleted(self):
        order = self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        order.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        ).action_cancel()
        order.action_cancel()

        session.line_ids.filtered(
            lambda l: l.sale_order_id == order
        ).unlink()
        session.invalidate_recordset(['so_count'])
        self.assertEqual(
            session.so_count, 0,
            'sin líneas, un pedido cancelado deja de contar',
        )

    def test_box_diff_and_box_match_unaffected_by_so_count_fix(self):
        for _ in range(3):
            self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        self.assertEqual(session.so_count, 3)
        self.assertEqual(session.box_diff, 0)
        self.assertTrue(session.box_match)

    def test_so_count_falls_back_to_picking_query_when_no_lines(self):
        """Sesión sin líneas (vacía/borrador): queda el cálculo viejo
        por pickings/fecha, sin tocar."""
        self._create_stray_done_picking()
        session = self._create_session()
        self.assertFalse(session.line_ids)
        self.assertEqual(session.so_count, 1)

    def test_action_view_lines_domain_matches_total_lines_count(self):
        for _ in range(4):
            self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        action = session.action_view_lines()
        domain = action['domain']
        self.assertEqual(domain, [('wizard_id', '=', session.id)])
        self.assertEqual(
            self.env['guapante.preparation.day.line'].search_count(domain),
            session.total_lines,
        )

    def test_action_view_lines_binds_the_dedicated_list_view(self):
        """Tech Lead, 2026-10-31: sin fijar la vista explícitamente,
        Odoo podría elegir otra lista registrada para el modelo y
        dejar view_preparation_day_line_list sin uso."""
        session = self._create_session()
        action = session.action_view_lines()
        expected_view = self.env.ref(
            'ist_preparation_day.view_preparation_day_line_list'
        )
        self.assertEqual(
            action['views'], [(expected_view.id, 'list')],
        )
