# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _date_to_utc_range,
)


@tagged('post_install', '-at_install')
class TestPreparationDayRenumbering(TransactionCase):
    """Eliminación de _guapante_renumber_session (David/Tech Lead,
    2026-11-03), a raíz del incidente de producción con el pedido
    S15245: una orden reubicada manualmente de la sesión de mañana a
    la de hoy debía tomar el siguiente número append-only (#73) y en
    cambio terminó en #53, desplazando otras cajas — causa raíz: el
    renumerador reshuffleaba TODAS las órdenes no pesadas de la sesión
    (ordenadas por id de creación, no por llegada) cada vez que
    entraba/se reubicaba/se reparaba una orden, inmediatamente
    deshaciendo la asignación MAX+1 correcta que
    sale_order._assign_daily_sequences() ya había hecho.

    Esta clase prueba la garantía que queda en su lugar: numeración
    estrictamente append-only (MAX+1), sin excepción y sin importar la
    hora del día — una orden que ya tiene daily_sequence > 0 nunca se
    vuelve a tocar, para nadie, nunca. Usa pedidos confirmados reales
    (con picking interno) porque _assign_daily_sequences() solo mira
    stock.picking — la fixture directa de línea sin picking que usaba
    el renumerador eliminado ya no aplica a este archivo.
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
            fields.Date.context_today(cls.env['sale.order']), days=110,
        )

    def _order_on_day(self, day=None):
        """Pedido confirmado real, con su picking interno reprogramado
        al día de prueba — dispara action_confirm()/
        _guapante_add_confirmed_order() (altas) o
        _guapante_relocate_picking() (si ya existía en otro día), el
        mismo camino que producción."""
        day = day or self.day
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        order.action_confirm()
        dt_start, _dt_end = _date_to_utc_range(self.env, day)
        pick = order.picking_ids.filtered(
            lambda p: (
                p.picking_type_code == 'internal'
                and p.state not in ('done', 'cancel')
            )
        )
        if pick.scheduled_date != dt_start:
            pick.scheduled_date = dt_start
        return order, pick

    def _line_for(self, order):
        return self.env['guapante.preparation.day.line'].sudo().search(
            [('sale_order_id', '=', order.id)],
        )

    # ── Garantía central: append-only, nunca se toca lo ya asignado ──

    def test_new_orders_never_change_existing_numbers(self):
        """Regresión directa de S15245: llegan pedidos nuevos uno tras
        otro — cada uno toma MAX+1 y ninguno de los anteriores cambia
        de número."""
        order_1, _p1 = self._order_on_day()
        self.assertEqual(order_1.daily_sequence, 1)

        order_2, _p2 = self._order_on_day()
        order_1.invalidate_recordset()
        self.assertEqual(order_1.daily_sequence, 1, 'no se toca al llegar order_2')
        self.assertEqual(order_2.daily_sequence, 2)

        order_3, _p3 = self._order_on_day()
        order_1.invalidate_recordset()
        order_2.invalidate_recordset()
        self.assertEqual(order_1.daily_sequence, 1, 'no se toca al llegar order_3')
        self.assertEqual(order_2.daily_sequence, 2, 'no se toca al llegar order_3')
        self.assertEqual(order_3.daily_sequence, 3)

    def test_weighed_and_unweighed_orders_equally_protected(self):
        """La garantía de no tocar un número ya asignado no depende de
        si la orden está pesada (is_done) — antes solo las pesadas
        ("fijas") estaban a salvo del reshuffle; ahora TODAS lo están,
        pesadas o no, porque ya no hay reshuffle."""
        order_1, _p1 = self._order_on_day()
        order_2, _p2 = self._order_on_day()
        line_2 = self._line_for(order_2)
        line_2.sudo().write({'actual_kg': 1.0, 'is_done': True})

        order_3, _p3 = self._order_on_day()

        order_1.invalidate_recordset()
        order_2.invalidate_recordset()
        self.assertEqual(order_1.daily_sequence, 1, 'no pesada — tampoco se toca')
        self.assertEqual(order_2.daily_sequence, 2, 'pesada — nunca se tocaba')
        self.assertEqual(order_3.daily_sequence, 3)

    def test_gap_from_manual_high_number_is_never_compressed(self):
        """daily_sequence nunca se asume contiguo en ningún lugar del
        código (verificado por grep) — si un número queda con un
        hueco abajo (ajuste manual, dato histórico irregular), una
        orden nueva NUNCA lo rellena ni comprime la numeración, solo
        toma MAX+1 real."""
        order_1, _p1 = self._order_on_day()
        self.assertEqual(order_1.daily_sequence, 1)
        order_1.sudo().daily_sequence = 5  # hueco manual 2,3,4.

        order_2, _p2 = self._order_on_day()

        order_1.invalidate_recordset()
        self.assertEqual(order_1.daily_sequence, 5, 'el ajuste manual no se toca')
        self.assertEqual(
            order_2.daily_sequence, 6,
            'MAX(5)+1 = 6 — nunca se inventa un 2 para llenar el hueco',
        )

    def test_idempotent_running_twice_gives_same_result(self):
        """Correr _assign_daily_sequences de nuevo sobre el mismo día
        (ej. una segunda llamada desde otro camino) no cambia nada —
        las órdenes ya tienen número y se saltan."""
        order_1, _p1 = self._order_on_day()
        order_2, _p2 = self._order_on_day()
        before = (order_1.daily_sequence, order_2.daily_sequence)

        self.env['sale.order']._assign_daily_sequences(self.day)

        order_1.invalidate_recordset()
        order_2.invalidate_recordset()
        after = (order_1.daily_sequence, order_2.daily_sequence)
        self.assertEqual(before, after)

    # ── Cancelado: número ocupado para siempre, nunca se reutiliza ──

    def test_cancelled_order_number_never_reused(self):
        cancelled, pick = self._order_on_day()
        self.assertEqual(cancelled.daily_sequence, 1)
        # action_cancel() en una orden ya confirmada solo devuelve la
        # acción del wizard de cancelación — _action_cancel() es el
        # método real que sí pone state='cancel'.
        cancelled.sudo()._action_cancel()

        order_2, _p2 = self._order_on_day()

        cancelled.invalidate_recordset()
        self.assertEqual(cancelled.daily_sequence, 1, 'la cancelada conserva su número')
        self.assertEqual(
            order_2.daily_sequence, 2,
            'MAX incluye TODOS los estados (incluso cancelado) — nunca se reutiliza el 1',
        )

    def test_cancelled_order_with_weighed_line_number_never_reused(self):
        """Corrección de Tech Lead (2026-10-30), todavía vigente: una
        cancelada que ya estaba pesada antes de cancelarse sigue
        contando su número como ocupado para siempre — un solo
        conteo, no doble."""
        cancelled, pick = self._order_on_day()
        line = self._line_for(cancelled)
        line.sudo().write({'actual_kg': 1.0, 'is_done': True})
        cancelled.sudo()._action_cancel()

        order_2, _p2 = self._order_on_day()

        cancelled.invalidate_recordset()
        self.assertEqual(cancelled.daily_sequence, 1)
        self.assertEqual(order_2.daily_sequence, 2)

    # ── El renumerador ya no existe — guardia explícita de regresión ──

    def test_renumber_session_method_was_removed(self):
        Session = self.env['guapante.preparation.day']
        self.assertFalse(
            hasattr(Session, '_guapante_renumber_session'),
            '_guapante_renumber_session debía eliminarse por completo '
            '(David/Tech Lead, 2026-11-03) — si esto falla, alguien lo '
            'reintrodujo.',
        )
