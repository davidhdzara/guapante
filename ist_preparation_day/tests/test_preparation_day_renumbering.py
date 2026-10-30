# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _date_to_utc_range,
)


@tagged('post_install', '-at_install')
class TestPreparationDayRenumbering(TransactionCase):
    """Plan de carga automática, paso e3 (2026-10-30): algoritmo de
    renumeración FIJA/FLEXIBLE (_guapante_renumber_session).

    Fixture directa (orden + línea, sin pasar por action_confirm() ni
    action_load()) para controlar con precisión qué queda FIJO,
    FLEXIBLE o CANCELADO — la integración real con e2 (alta
    incremental al confirmar) y con la reubicación ya está cubierta en
    test_sale_order_auto_load.py y test_preparation_day_relocation.py.
    Una orden en 'draft' sin picking es suficiente: el algoritmo solo
    mira line_ids/is_done para fijas/flexibles, y una consulta aparte
    a stock.picking (con picking real) para canceladas.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner Renumber',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Product Renumber Test',
            'type': 'consu',
            'list_price': 1000.0,
        })
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse Renumber',
                'code': 'TWRN',
                'company_id': cls.env.company.id,
            })
        cls.warehouse.delivery_steps = 'pick_ship'
        # Ventana lejana, propia de este archivo — no choca con otros
        # tests/datos reales.
        cls.day = fields.Date.add(
            fields.Date.context_today(cls.env['sale.order']), days=100,
        )

    def _session(self):
        return self.env[
            'guapante.preparation.day'
        ]._ensure_session_for_date(self.day)

    def _order(self, daily_sequence=0):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        if daily_sequence:
            order.sudo().daily_sequence = daily_sequence
        return order

    def _line(self, session, order, is_done=False):
        return self.env['guapante.preparation.day.line'].create({
            'wizard_id': session.id,
            'sale_order_id': order.id,
            'product_product_id': self.product.id,
            'is_done': is_done,
        })

    def _confirm_and_cancel_with_number(self, number, mark_done=False):
        """Pedido cancelado real (con picking interno en self.day) con
        un número de caja ya asignado — necesario para el test de
        cancelados, que consulta stock.picking de verdad.
        mark_done=True simula que ya se había pesado ANTES de
        cancelarse (caso de doble conteo, Tech Lead 2026-10-30)."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        order.action_confirm()
        dt_start, _dt_end = _date_to_utc_range(self.env, self.day)
        Picking = order.picking_ids.filtered(
            lambda p: (
                p.picking_type_code == 'internal'
                and p.state not in ('done', 'cancel')
            )
        )
        Picking.scheduled_date = dt_start
        order.sudo().daily_sequence = number
        if mark_done:
            Lines = self.env['guapante.preparation.day.line'].sudo().search(
                [('sale_order_id', '=', order.id)],
            )
            Lines.sudo().write({'is_done': True})
        # action_cancel() en una orden ya confirmada solo devuelve la
        # acción del wizard de cancelación (no cancela nada por sí
        # solo) — _action_cancel() es el método real que sí pone
        # state='cancel', lo que llama el wizard por debajo.
        order.sudo()._action_cancel()
        return order

    # ── Ejemplo de David: 6 cajas, #2 y #5 ya pesadas, llega 1 nueva ──

    def test_example_6_boxes_two_fixed(self):
        session = self._session()
        orders = [self._order() for _ in range(6)]
        for i, order in enumerate(orders, start=1):
            order.sudo().daily_sequence = i
            self._line(session, order, is_done=(i in (2, 5)))
        new_order = self._order()
        self._line(session, new_order, is_done=False)

        session._guapante_renumber_session()

        fixed_ids = {orders[1].id, orders[4].id}
        self.assertEqual(orders[1].daily_sequence, 2)
        self.assertEqual(orders[4].daily_sequence, 5)

        flexible = [o for o in orders if o.id not in fixed_ids] + [new_order]
        flexible_sorted = sorted(flexible, key=lambda o: o.id)
        available = [1, 3, 4, 6, 7]
        for order, expected in zip(flexible_sorted, available):
            self.assertEqual(
                order.daily_sequence, expected,
                f'orden id={order.id} debería quedar en #{expected}',
            )

    def test_gap_from_high_fixed_number_is_not_compressed(self):
        """Caso borde explícito del plan: si un número fijo alto deja
        más huecos bajos que flexibles para llenarlos, el hueco queda
        — no se comprime la numeración."""
        session = self._session()
        orders = [self._order() for _ in range(3)]
        orders[0].sudo().daily_sequence = 1
        orders[1].sudo().daily_sequence = 2
        orders[2].sudo().daily_sequence = 5  # fija, con número alto
        self._line(session, orders[0], is_done=False)
        self._line(session, orders[1], is_done=False)
        self._line(session, orders[2], is_done=True)

        session._guapante_renumber_session()

        self.assertEqual(orders[2].daily_sequence, 5)
        # N = 3 (1 fija + 2 flexibles) → disponibles = {1,2,3}: nunca
        # se inventa un 4 para "acercar" el hueco a la fija de arriba.
        self.assertEqual(
            sorted([orders[0].daily_sequence, orders[1].daily_sequence]),
            [1, 2],
        )

    # ── Cancelado (Tech Lead, 2026-10-30): número ocupado para siempre ──

    def test_cancelled_order_number_never_reused(self):
        cancelled = self._confirm_and_cancel_with_number(3)
        session = self._session()
        orders = [self._order() for _ in range(3)]
        for order in orders:
            self._line(session, order, is_done=False)

        session._guapante_renumber_session()

        self.assertEqual(cancelled.daily_sequence, 3)
        new_numbers = sorted(o.daily_sequence for o in orders)
        self.assertNotIn(3, new_numbers)
        # N = 1 cancelada + 3 flexibles = 4 → disponibles {1,2,4}.
        self.assertEqual(new_numbers, [1, 2, 4])

    def test_cancelled_order_line_not_double_counted_as_flexible(self):
        """Si la línea de la cancelada todavía no se limpió (limpieza
        perezosa, solo en el próximo action_load), no debe contarse
        dos veces — ni como ocupada Y como flexible. La línea "vieja"
        ya queda puesta sola por _confirm_and_cancel_with_number (el
        confirm+reubicación reales la crean) — no se duplica a mano."""
        cancelled = self._confirm_and_cancel_with_number(2)
        session = self._session()
        self.assertIn(
            cancelled, session.line_ids.mapped('sale_order_id'),
            'la línea vieja de la cancelada debe seguir presente, sin '
            'limpiar, para que el test ejercite el caso real',
        )
        order = self._order()
        self._line(session, order, is_done=False)

        session._guapante_renumber_session()

        self.assertEqual(cancelled.daily_sequence, 2)
        self.assertEqual(order.daily_sequence, 1)

    def test_cancelled_order_with_weighed_line_not_double_counted(self):
        """Corrección de Tech Lead (2026-10-30): una cancelada que YA
        estaba pesada antes de cancelarse cae en FixedOrders Y en
        cancelled_numbers a la vez (mismo número) — sumar los dos
        conteos por separado inflaba `total` y repartía un número de
        más a alguna flexible."""
        cancelled = self._confirm_and_cancel_with_number(2, mark_done=True)
        session = self._session()
        orders = [self._order() for _ in range(3)]
        for order in orders:
            self._line(session, order, is_done=False)

        session._guapante_renumber_session()

        self.assertEqual(cancelled.daily_sequence, 2)
        new_numbers = sorted(o.daily_sequence for o in orders)
        # Con el bug: total = 1 (fija) + 1 (cancelada) + 3 = 5 →
        # disponibles {1,3,4,5}, un hueco de más. Corregido: total =
        # 1 (ocupado único) + 3 = 4 → disponibles {1,3,4}.
        self.assertEqual(new_numbers, [1, 3, 4])
        self.assertNotIn(5, new_numbers)

    # ── Fija con trabajo en curso: solo el número cambia, nada más ──

    def test_fixed_box_claim_in_progress_untouched_only_number_fixed(self):
        session = self._session()
        fixed_order = self._order(daily_sequence=1)
        fixed_line = self._line(session, fixed_order, is_done=True)
        flexible_order = self._order(daily_sequence=2)
        self._line(session, flexible_order, is_done=False)
        new_order = self._order()
        self._line(session, new_order, is_done=False)

        session._guapante_renumber_session()

        self.assertEqual(fixed_order.daily_sequence, 1)
        self.assertTrue(fixed_line.is_done)
        self.assertEqual(
            sorted([flexible_order.daily_sequence, new_order.daily_sequence]),
            [2, 3],
        )

    def test_idempotent_running_twice_gives_same_result(self):
        session = self._session()
        orders = [self._order() for _ in range(4)]
        for order in orders:
            self._line(session, order, is_done=False)
        session._guapante_renumber_session()
        first_pass = sorted(o.daily_sequence for o in orders)
        session._guapante_renumber_session()
        second_pass = sorted(o.daily_sequence for o in orders)
        self.assertEqual(first_pass, second_pass)

    def test_summary_note_posted_once_on_session_chatter(self):
        """Condición 6 del plan: una sola nota-resumen en el chatter
        de la sesión cuando hay cambios."""
        session = self._session()
        order = self._order(daily_sequence=5)  # va a bajar a 1
        self._line(session, order, is_done=False)
        messages_before = len(session.message_ids)

        session._guapante_renumber_session()

        self.assertEqual(order.daily_sequence, 1)
        session.invalidate_recordset()
        self.assertEqual(len(session.message_ids), messages_before + 1)
        self.assertIn('renumeradas', session.message_ids[0].body or '')

    def test_no_notes_posted_when_nothing_changes(self):
        session = self._session()
        orders = [self._order() for _ in range(3)]
        for order in orders:
            self._line(session, order, is_done=False)
        session._guapante_renumber_session()
        messages_before = len(session.message_ids)
        session._guapante_renumber_session()  # segunda pasada, sin cambios
        session.invalidate_recordset()
        self.assertEqual(len(session.message_ids), messages_before)

    def test_per_box_note_posted_on_its_own_picking(self):
        """Condición 6 del plan: nota corta individual en el picking
        de CADA caja renumerada — requiere un picking real."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        order.action_confirm()
        dt_start, _dt_end = _date_to_utc_range(self.env, self.day)
        Picking = order.picking_ids.filtered(
            lambda p: (
                p.picking_type_code == 'internal'
                and p.state not in ('done', 'cancel')
            )
        )
        # Dispara la reubicación existente hacia self.day — e2/e3 ya
        # corren solos acá y dejan el número correcto (#1, única
        # orden). Se fuerza un número "equivocado" después para que
        # la siguiente renumeración manual tenga algo que corregir y
        # de verdad publique la nota.
        Picking.scheduled_date = dt_start
        session = self._session()
        order.sudo().daily_sequence = 99
        messages_before = len(Picking.message_ids)

        session._guapante_renumber_session()

        self.assertEqual(order.daily_sequence, 1)
        Picking.invalidate_recordset()
        new_messages = Picking.message_ids.sorted('id', reverse=True)[
            :len(Picking.message_ids) - messages_before
        ]
        self.assertTrue(
            any('pasó a #1' in (m.body or '') for m in new_messages)
        )
