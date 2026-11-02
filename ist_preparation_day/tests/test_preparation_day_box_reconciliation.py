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
from unittest.mock import patch

import odoo.sql_db as sql_db
from odoo import fields
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

    def test_so_count_and_progress_use_a_bounded_number_of_queries(self):
        """Tech Lead, 2026-11-02: leer so_count/total_lines/done_lines de
        varias sesiones a la vez no debe crecer con la cantidad de
        sesiones — antes de la consulta agregada, cada sesión disparaba
        su propio search() sobre line_ids (144 consultas para 80
        sesiones, medido en staging_main)."""
        sessions = self.env['guapante.preparation.day']
        for _ in range(3):
            self._create_confirmed_order(qty=1.0)
            session = self._create_session()
            session.action_load()
            sessions |= session
            self.delivery_date = fields.Date.add(self.delivery_date, days=1)

        sessions.invalidate_recordset(['so_count', 'total_lines', 'done_lines'])
        before = sql_db.sql_counter
        sessions.mapped('so_count')
        sessions.mapped('total_lines')
        sessions.mapped('done_lines')
        after = sql_db.sql_counter
        # 7 medido con 3 sesiones (2 _read_group, más chequeos de acceso
        # y refresco de otros campos dependientes) — el número exacto
        # importa menos que el techo: fijo pase lo que pase con la
        # cantidad de sesiones, no ~3-5 consultas POR sesión como antes
        # (eso daría ~144 para 80 sesiones, medido en staging_main).
        self.assertLessEqual(
            after - before, 10,
            "so_count/total_lines/done_lines de varias sesiones deben "
            "resolverse con un número fijo de consultas, no uno por sesión",
        )

    def test_reading_so_count_does_not_trigger_draft_count_search(self):
        """Tech Lead, 2026-11-02: draft_count vive en su PROPIO compute
        (_compute_draft_count) — antes compartía compute con so_count,
        así que pedir so_count (lo que hace la lista de Sesiones)
        disparaba también la búsqueda de sale.order draft/sent de
        draft_count, aunque nadie lo pidiera. Separados, leer so_count/
        total_lines no debe tocar _compute_draft_count para nada."""
        sessions = self.env['guapante.preparation.day']
        for _ in range(3):
            self._create_confirmed_order(qty=1.0)
            session = self._create_session()
            session.action_load()
            sessions |= session
            self.delivery_date = fields.Date.add(self.delivery_date, days=1)

        sessions.invalidate_recordset(
            ['so_count', 'total_lines', 'done_lines', 'draft_count']
        )
        PreparationDay = type(sessions)
        with patch.object(
            PreparationDay, '_compute_draft_count',
            side_effect=AssertionError(
                '_compute_draft_count no debe correr al leer '
                'so_count/total_lines/done_lines'
            ),
        ):
            sessions.mapped('so_count')
            sessions.mapped('total_lines')
            sessions.mapped('done_lines')

    def test_draft_count_split_keeps_the_same_value_as_before(self):
        """Tech Lead, 2026-11-02: separar draft_count a su propio
        compute no debe cambiar el valor que calcula — solo DÓNDE
        corre. Hallazgo aparte (no se toca en este ítem): expected_date
        en sale.order es un campo no-almacenado sin método search()
        propio — Odoo registra error y lo ignora generando un leaf
        vacío (dummy True), así que esa mitad del OR con date_order
        queda siempre verdadera y draft_count termina contando TODAS
        las cotizaciones draft/sent de la base, sin filtrar por fecha
        de la sesión. Este test fija ese comportamiento actual (buggy
        pero sin cambios por este refactor), no lo valida como
        correcto."""
        total_draft_sent = self.env['sale.order'].sudo().search_count(
            [('state', 'in', ('draft', 'sent'))]
        )
        self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product_weight.id,
                'product_uom_qty': 1.0,
            })],
        })
        total_draft_sent += 1

        # Fecha sin ninguna relación con la cotización recién creada —
        # si el filtro de fecha funcionara, draft_count no debería
        # incluirla.
        unrelated_session = self.env['guapante.preparation.day'].create({
            'date': '2000-01-01',
        })
        self.assertEqual(
            unrelated_session.draft_count, total_draft_sent,
            "draft_count hoy ignora la fecha de la sesión (hallazgo "
            "aparte, sin tocar) — debe seguir igual tras el refactor",
        )

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

    def test_action_view_lines_binds_the_dedicated_search_view(self):
        """Entrega A del buscador (David/Tech Lead, 2026-11-01): la
        acción del botón "Líneas" debe fijar su propia vista de
        búsqueda, no la que Odoo elija por defecto para el modelo."""
        session = self._create_session()
        action = session.action_view_lines()
        expected_search_view = self.env.ref(
            'ist_preparation_day.view_preparation_day_line_search'
        )
        self.assertEqual(
            action['search_view_id'],
            [expected_search_view.id, expected_search_view.name],
        )

    def test_line_search_view_pending_done_filters_match_is_done(self):
        """Los filtros "Pendientes"/"Terminadas" de
        view_preparation_day_line_search deben coincidir exactamente con
        is_done, sin importar cuántas líneas haya de cada lado."""
        for _ in range(3):
            self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        Line = self.env['guapante.preparation.day.line']
        done_line = session.line_ids[0]
        done_line.write({'actual_kg': 1.0, 'is_done': True})

        pending_domain = [('wizard_id', '=', session.id), ('is_done', '=', False)]
        done_domain = [('wizard_id', '=', session.id), ('is_done', '=', True)]
        self.assertEqual(
            Line.search_count(pending_domain), len(session.line_ids) - 1,
        )
        self.assertEqual(Line.search_count(done_domain), 1)

    def test_line_search_view_fields_exist_on_model(self):
        """Los 4 campos de búsqueda (producto, caja #, pedido, cliente) y
        los 4 de "Agrupar Por" (producto, cliente, zona, caja) deben
        existir como campos reales del modelo — si alguno se renombra,
        este test debe fallar antes que la vista en producción."""
        Line = self.env['guapante.preparation.day.line']
        for field_name in (
            'product_description', 'daily_sequence', 'order_name',
            'main_customer_name', 'product_id', 'zone_name',
        ):
            self.assertIn(field_name, Line._fields)
