# -*- coding: utf-8 -*-
"""ESPEJO Inventario→Preparación (David/Tech Lead, 2026-11-05).

Caso origen (confirmado con datos reales en producción, 2026-11-05):
el traslado Recolectar (PICK) de una línea se valida por fuera del
flujo de Preparación — directo desde Inventario, con o sin peso — y
la línea de guapante.preparation.day.line queda Pendiente para
siempre porque nada la refleja. Cubre el hook liviano de
stock_move.py (_action_done → needs_inventory_mirror) y el cron
_cron_mirror_inventory_to_preparation (preparation_day.py).

NOTA (2026-11-05): corrido contra la suite real en staging_dev — 2
fallas encontradas y corregidas: (1) el hook de stock_move.py
excluía is_done=True, matando la comparación de la decisión (c); (2)
el test de "validar en 0 desde Inventario" asumía un camino que Odoo
bloquea (_sanity_check rechaza validar un traslado sin cantidades
reservadas/pickeadas) — no hay tablet-equivalente de E7 para un PICK
validado directo desde Inventario, se eliminó ese test.
"""
from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)

_SYNC_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day.models.preparation_day'
    '.PreparationDayLine._sync_weight_to_stock'
)


@tagged('post_install', '-at_install')
class TestMirrorInventoryToPreparation(TestPreparationDay):

    def _line_for(self, order):
        return self.env['guapante.preparation.day.line'].sudo().search(
            [('sale_order_id', '=', order.id)],
        )

    def _pick_for(self, order):
        return order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal'
            and p.state not in ('done', 'cancel')
        )

    def _validate_pick_from_inventory(self, order, weight):
        """Simula validar el traslado Recolectar directo desde
        Inventario, SIN pasar por Preparación: pone la cantidad a
        mano en el move (mismo contexto que ya inyecta button_validate
        para cualquier Recolectar — manual_entry/skip_recolectar_
        zero_check, ver theme_guapante/models/stock_picking.py) y
        llama _action_done() directo — el mismo punto de entrada real
        que usa button_validate() tras sus propios wizards, sin pelear
        acá con esos wizards."""
        pick = self._pick_for(order)
        move = pick.move_ids[:1]
        ctx = {'manual_entry': True, 'skip_recolectar_zero_check': True}
        move.with_context(**ctx).write({
            'quantity': weight,
            'picked': True,
            'is_weight_confirmed': True,
        })
        if move.move_line_ids:
            move.move_line_ids[0].with_context(**ctx).write({
                'quantity': weight, 'picked': True,
            })
        move._action_done()
        return move

    def test_validate_from_inventory_with_weight_closes_line_via_cron(self):
        """Caso real (producción, 2026-11-05): PICK validado desde
        Inventario con peso > 0, sin operario — el cron debe cerrar
        la línea con ese peso, sin operario asociado."""
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = self._line_for(order)
        self.assertFalse(line.is_done)

        self._validate_pick_from_inventory(order, 2.8)

        line.invalidate_recordset()
        self.assertTrue(
            line.needs_inventory_mirror,
            'el hook de _action_done debe marcar la línea para el cron',
        )

        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()

        line.invalidate_recordset()
        self.assertTrue(line.is_done)
        self.assertEqual(line.actual_kg, 2.8)
        self.assertFalse(line.done_by_employee_id)
        self.assertFalse(line.needs_inventory_mirror)

    def test_closes_line_without_reopening_an_already_done_session(self):
        """'Sesiones cerradas → terminar línea sin reabrirla' (David/
        Tech Lead): si la sesión ya está 'done' cuando corre el cron,
        se queda 'done' — no se reabre ni se vuelve a marcar done."""
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = self._line_for(order)

        # Forzar la sesión a 'done' con la línea todavía pendiente
        # (simula el caso real visto en producción: sesión 221 'done'
        # con 4 líneas atascadas).
        session.sudo().write({'state': 'done'})
        message_count_before = len(session.message_ids)

        self._validate_pick_from_inventory(order, 1.5)
        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()

        line.invalidate_recordset()
        session.invalidate_recordset()
        self.assertTrue(line.is_done)
        self.assertEqual(session.state, 'done')
        # Una sola nota nueva (la de "cerrada automáticamente"), no una
        # segunda de action_mark_done.
        self.assertEqual(len(session.message_ids), message_count_before + 1)

    def test_operator_closes_first_cron_leaves_it_untouched_and_notes_diff(self):
        """Decisión (c): gana quien llegó primero. Si el operario ya
        cerró la línea (tablet/Productos) antes de que el PICK se
        valide desde Inventario, el cron NUNCA pisa is_done/actual_kg
        — si el peso difiere, solo deja una nota en el chatter."""
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = self._line_for(order)

        # El operario cierra la línea primero, desde Productos.
        line.sudo().write({'actual_kg': 3.0, 'is_done': True})
        message_count_before = len(session.message_ids)

        # El PICK se valida después desde Inventario con un valor
        # distinto (ej. alguien reconfirma el pesaje físico).
        self._validate_pick_from_inventory(order, 2.9)
        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()

        line.invalidate_recordset()
        session.invalidate_recordset()
        self.assertTrue(line.is_done)
        self.assertEqual(
            line.actual_kg, 3.0,
            'el valor del operario, que llegó primero, nunca se pisa',
        )
        self.assertEqual(
            len(session.message_ids), message_count_before + 1,
            'debe quedar UNA nota nueva señalando la diferencia',
        )
        last_note = session.message_ids.sorted('id', reverse=True)[0]
        self.assertIn('Diferencia de peso', last_note.body)

    def test_move_cancelled_closes_line_at_zero_via_cron(self):
        """Extensión (Tech Lead/David, 2026-11-06) — hueco encontrado
        en producción (sesión 226): un PICK que se CANCELA (ej.
        "sin stock", declinar backorder) sin que Preparación la haya
        cerrado antes nunca pasa por _action_done, así que el hook
        viejo nunca prendía needs_inventory_mirror y la línea quedaba
        Pendiente para siempre. El nuevo hook en _action_cancel()
        (stock_move.py) + _guapante_mirror_from_cancelled_move()
        deben cerrarla igual que el caso 'done' sin operario, pero
        SIEMPRE en actual_kg=0 (un move cancelado no tiene un peso
        real despachado que leer)."""
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = self._line_for(order)
        self.assertFalse(line.is_done)

        pick = self._pick_for(order)
        pick.action_cancel()

        line.invalidate_recordset()
        self.assertTrue(
            line.needs_inventory_mirror,
            'el hook de _action_cancel debe marcar la línea para el cron',
        )

        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()

        line.invalidate_recordset()
        self.assertTrue(line.is_done)
        self.assertEqual(line.actual_kg, 0.0)
        self.assertFalse(line.done_by_employee_id)
        self.assertFalse(line.needs_inventory_mirror)

    def test_order_cancelled_entirely_removes_line_never_closes_it(self):
        """Guard (David, vía Tech Lead; lote 3, 2026-11-09): si el
        PEDIDO ENTERO se cancela, la cancelación en cascada de su PICK
        no es una decisión de despacho — la línea NUNCA se cierra en 0
        (no hubo despacho): desaparece de la sesión y queda una nota
        con nombres. Antes (2026-11-06) se dejaba pendiente con «revisar
        manualmente»; David pidió que desaparezca sola."""
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = self._line_for(order)
        move = line.stock_move_id

        # Cascada real de sale_stock: cancela primero pickings/moves
        # (prende nuestro hook) y DESPUÉS pone el pedido en 'cancel';
        # el override de _action_cancel retira la línea al terminar.
        order._action_cancel()
        self.assertEqual(order.state, 'cancel')

        self.assertFalse(line.exists(), 'la línea desaparece de la sesión')
        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()
        session.invalidate_recordset()
        notes = ' '.join(session.message_ids.mapped('body'))
        self.assertIn(f'Pedido {order.name} cancelado', notes)
        self.assertNotIn('no cerrada', notes)
        self.assertEqual(move.state, 'cancel', 'Inventario queda en Cancelado')

    def test_order_cancelled_when_immediate_removal_failed_cron_removes_it(self):
        """Red de seguridad: si el retiro inmediato falló (o el pedido se
        canceló por otra ruta), el barrido del cron del espejo la retira
        — nunca la cierra en 0."""
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = self._line_for(order)

        with patch(
            'odoo.addons.ist_preparation_day.models.preparation_day'
            '.PreparationDay._guapante_remove_cancelled_lines_in_session',
            side_effect=RuntimeError('boom'),
        ):
            order._action_cancel()
        self.assertEqual(order.state, 'cancel')
        self.assertTrue(line.exists(), 'el retiro inmediato falló: sigue ahí')

        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()

        self.assertFalse(line.exists(), 'el cron la retira')
        notes_after = len(session.message_ids)
        # idempotente: otra corrida no repite notas ni falla
        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()
        self.assertEqual(len(session.message_ids), notes_after)

    def test_cron_sweep_ignores_closed_sessions_and_does_not_spam_notes(self):
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = self._line_for(order)
        session.write({'state': 'done'})
        order._action_cancel()
        notes = len(session.message_ids)
        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()
        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()
        self.assertTrue(line.exists(), 'sesión cerrada: nunca se borra')
        self.assertEqual(len(session.message_ids), notes, 'el barrido no repite notas')

    def test_already_done_line_not_overwritten_by_cancelled_move(self):
        """Decisión (c), simétrica al caso 'done': si Preparación ya
        había cerrado la línea antes de que el PICK se cancele (ej.
        un admin cancela el traslado después de que el operario ya
        despachó), el cron nunca pisa is_done/actual_kg."""
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        line = self._line_for(order)

        line.sudo().write({'actual_kg': 3.0, 'is_done': True})

        pick = self._pick_for(order)
        pick.action_cancel()

        self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()

        line.invalidate_recordset()
        self.assertTrue(line.is_done)
        self.assertEqual(
            line.actual_kg, 3.0,
            'el valor del operario, que llegó primero, nunca se pisa',
        )
        self.assertFalse(line.needs_inventory_mirror)

    def test_cancel_mirror_never_calls_sync_weight_to_stock(self):
        """Regresión explícita, simétrica a la del caso 'done' (Tech
        Lead, riesgo #8 del diseño): el camino del cron para un move
        cancelado NUNCA debe llamar _sync_weight_to_stock — volvería
        a escribir el move y el hook de stock_move.py lo marcaría de
        nuevo."""
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()

        pick = self._pick_for(order)
        pick.action_cancel()

        with patch(_SYNC_PATCH_TARGET) as mocked_sync:
            self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()
            mocked_sync.assert_not_called()

    def test_mirror_never_calls_sync_weight_to_stock(self):
        """Regresión explícita contra el bucle con _sync_weight_to_
        stock (Tech Lead, riesgo #8 del diseño): el camino del cron
        NUNCA debe llamar ese método — volvería a escribir el move y
        el hook de stock_move.py lo marcaría de nuevo."""
        order = self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()

        self._validate_pick_from_inventory(order, 1.0)

        with patch(_SYNC_PATCH_TARGET) as mocked_sync:
            self.env['guapante.preparation.day.line']._cron_mirror_inventory_to_preparation()
            mocked_sync.assert_not_called()
