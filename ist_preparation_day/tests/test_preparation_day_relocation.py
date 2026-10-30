# -*- coding: utf-8 -*-
"""Tests de la Regla de la jornada (David, 2026-10-29): la sesión de
la fecha D son los PICK cuyo scheduled_date cae en el día calendario D
(hora Bogotá), sin corte horario, y mover un PICK pendiente entre días
reubica su línea de preparación de forma incremental.

Cubre el plan aprobado por Tech Lead (2026-10-29) sobre el hallazgo de
Caja #0 / reubicación — ver reporte en el hilo de sesiones.
"""
from datetime import datetime, time
from unittest.mock import patch

import pytz
from psycopg2 import errors as pg_errors

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _date_to_utc_range,
)


@tagged('post_install', '-at_install')
class TestPreparationDayRelocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse Reloc',
                'code': 'TWR',
                'company_id': cls.env.company.id,
            })
        cls.warehouse.delivery_steps = 'pick_ship'
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner Reloc',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Product Reloc Test',
            'type': 'consu',
            'list_price': 1000.0,
        })
        cls.product_2 = cls.env['product.product'].create({
            'name': 'Product Reloc Test 2',
            'type': 'consu',
            'list_price': 1000.0,
        })
        cls.product_3 = cls.env['product.product'].create({
            'name': 'Product Reloc Test 3',
            'type': 'consu',
            'list_price': 1000.0,
        })
        # Ventana lejana para no chocar con otros tests/datos reales.
        cls.day_a = fields.Date.add(
            fields.Date.context_today(cls.env['sale.order']), days=40,
        )
        cls.day_b = fields.Date.add(cls.day_a, days=3)

    def _create_confirmed_order(self, day):
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
            lambda p: p.picking_type_code == 'internal'
            and p.state not in ('done', 'cancel')
        )
        pick.scheduled_date = dt_start
        return order, pick

    def _load_session(self, day):
        Session = self.env['guapante.preparation.day'].sudo().search(
            [('date', '=', day)], limit=1,
        )
        if not Session:
            Session = self.env['guapante.preparation.day'].create(
                {'date': day},
            )
        Session.action_load()
        return Session

    def _line_for(self, order):
        return self.env['guapante.preparation.day.line'].sudo().search(
            [('sale_order_id', '=', order.id)],
        )

    # ── Mismo día, distinta hora: no reubica, no cambia número ──

    def test_same_calendar_day_different_hour_no_relocation(self):
        order, pick = self._create_confirmed_order(self.day_a)
        session_a = self._load_session(self.day_a)
        line = self._line_for(order)
        old_wizard_id = line.wizard_id.id
        old_seq = order.daily_sequence
        self.assertTrue(old_seq > 0)

        # Mover solo la hora, mismo día calendario.
        dt_start, _dt_end = _date_to_utc_range(self.env, self.day_a)
        pick.scheduled_date = dt_start.replace(hour=23, minute=0)

        line.invalidate_recordset()
        order.invalidate_recordset()
        self.assertEqual(line.wizard_id.id, old_wizard_id)
        self.assertEqual(order.daily_sequence, old_seq)
        self.assertEqual(session_a.line_ids, line)

    # ── Cambio de día: reubica y reasigna número ──

    def test_different_day_relocates_line_and_reassigns_sequence(self):
        order, pick = self._create_confirmed_order(self.day_a)
        session_a = self._load_session(self.day_a)
        line = self._line_for(order)
        old_seq = order.daily_sequence
        self.assertTrue(old_seq > 0)

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.scheduled_date = dt_start_b

        line.invalidate_recordset()
        order.invalidate_recordset()
        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        self.assertTrue(session_b, 'La sesión del día nuevo debe existir')
        self.assertEqual(line.wizard_id.id, session_b.id)
        self.assertNotIn(line, session_a.line_ids)
        self.assertTrue(order.daily_sequence > 0)
        # No tiene por qué ser el mismo número que en el día viejo —
        # lo que importa es que coincide con el de la línea (related).
        self.assertEqual(line.daily_sequence, order.daily_sequence)

    # ── Mover un pendiente nunca cargado crea la sesión destino vacía ──

    def test_moving_picking_from_a_closed_session_creates_draft_destination(self):
        """Renombrado (Tech Lead, 2026-10-30) — antes se llamaba
        test_moving_never_loaded_picking_creates_draft_session y
        probaba "nunca se llama action_load() para day_a, por eso no
        hay línea". Desde e2 (2026-10-29) eso ya no describe ningún
        escenario real: confirmar SIEMPRE intenta autopoblar la sesión
        de la fecha natural del PICK, llame o no alguien a
        action_load() a mano. El ÚNICO camino real hoy en que e2
        deja una sesión sin su línea es que esa sesión ya esté
        'done' — se fuerza la de self.day_a a 'done' ANTES de
        confirmar (vía fields.Datetime.now() fijo, no se deja a la
        suerte de qué sesión real sea 'hoy' en el servidor) para
        replicar ese único caso de forma controlada."""
        SessionA = self.env[
            'guapante.preparation.day'
        ]._ensure_session_for_date(self.day_a)
        SessionA.action_mark_done()

        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        bogota_tz = pytz.timezone('America/Bogota')
        fixed_now = bogota_tz.localize(
            datetime.combine(self.day_a, time(0, 10)),
        ).astimezone(pytz.utc).replace(tzinfo=None)
        with patch('odoo.fields.Datetime.now', return_value=fixed_now):
            order.action_confirm()
        pick = order.picking_ids.filtered(
            lambda p: (
                p.picking_type_code == 'internal'
                and p.state not in ('done', 'cancel')
            )
        )
        self.assertFalse(
            SessionA.line_ids,
            'e2 no debía agregar nada — la sesión ya estaba done',
        )

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.scheduled_date = dt_start_b

        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        self.assertTrue(session_b)
        self.assertEqual(session_b.state, 'draft')
        self.assertFalse(session_b.line_ids)

    # ── Summaries de las dos sesiones quedan correctos ──

    def test_relocation_patches_both_summaries(self):
        order, pick = self._create_confirmed_order(self.day_a)
        session_a = self._load_session(self.day_a)
        summary_a = session_a.summary_ids.filtered(
            lambda s: s.product_id == self.product,
        )
        self.assertEqual(summary_a.order_count, 1)

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.scheduled_date = dt_start_b

        summary_a.invalidate_recordset()
        self.assertFalse(
            summary_a.exists(),
            'El summary viejo debe desaparecer al quedar en 0 órdenes',
        )
        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        summary_b = session_b.summary_ids.filtered(
            lambda s: s.product_id == self.product,
        )
        self.assertEqual(summary_b.order_count, 1)

    # ── Línea ya pesada bloquea, aunque esté en OTRO picking de la misma orden ──

    def test_weighed_line_on_same_order_blocks_even_different_picking(self):
        order, pick = self._create_confirmed_order(self.day_a)
        self._load_session(self.day_a)
        line = self._line_for(order)
        line.write({'actual_kg': 1.0, 'is_done': True})

        # Picking SEPARADO ligado a la misma orden (simula backorder),
        # sin línea de preparación propia — el bloqueo debe venir de
        # la línea pesada de la orden, no de este picking puntual.
        other_pick = pick.copy({
            'sale_id': order.id,
            'move_ids': [],
        })
        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        with self.assertRaises(UserError):
            other_pick.write({'scheduled_date': dt_start_b})

    def test_weighed_line_blocks_its_own_picking(self):
        order, pick = self._create_confirmed_order(self.day_a)
        self._load_session(self.day_a)
        line = self._line_for(order)
        line.write({'actual_kg': 1.0, 'is_done': True})

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        with self.assertRaises(UserError):
            pick.write({'scheduled_date': dt_start_b})

        line.invalidate_recordset()
        pick.invalidate_recordset()
        self.assertTrue(line.is_done)

    # ── bus.bus avisa a las DOS sesiones ──

    def test_relocation_notifies_both_sessions_via_bus(self):
        order, pick = self._create_confirmed_order(self.day_a)
        session_a = self._load_session(self.day_a)

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        with patch.object(
            type(self.env['bus.bus']), '_sendone',
        ) as mock_sendone:
            pick.write({'scheduled_date': dt_start_b})

        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        channels_called = {call.args[0] for call in mock_sendone.call_args_list}
        self.assertIn(f'guapante_preparation_day-{session_a.id}', channels_called)
        self.assertIn(f'guapante_preparation_day-{session_b.id}', channels_called)

    # ── Condición 1 (Tech Lead): el bloqueo solo aplica si cambia el día ──

    def test_weighed_line_same_day_different_hour_does_not_block(self):
        order, pick = self._create_confirmed_order(self.day_a)
        self._load_session(self.day_a)
        line = self._line_for(order)
        line.write({'actual_kg': 1.0, 'is_done': True})

        dt_start, _dt_end = _date_to_utc_range(self.env, self.day_a)
        # No debe lanzar — mismo día calendario, solo cambia la hora.
        pick.write({'scheduled_date': dt_start.replace(hour=20, minute=0)})
        self.assertEqual(pick.scheduled_date.hour, 20)

    def test_weighed_line_rewriting_same_value_does_not_block(self):
        order, pick = self._create_confirmed_order(self.day_a)
        self._load_session(self.day_a)
        line = self._line_for(order)
        line.write({'actual_kg': 1.0, 'is_done': True})

        same_value = pick.scheduled_date
        # No debe lanzar — se reescribe exactamente el mismo valor.
        pick.write({'scheduled_date': same_value})

    # ── Condición 2 (Tech Lead): savepoint — un error en la ──
    # ── reubicación no debe tumbar la escritura del picking ──

    def test_relocation_failure_does_not_block_picking_write(self):
        order, pick = self._create_confirmed_order(self.day_a)
        session_a = self._load_session(self.day_a)
        line = self._line_for(order)
        messages_before = len(pick.message_ids)

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        with patch.object(
            type(self.env['guapante.preparation.day']), '_guapante_patch_summary',
            side_effect=Exception('fallo forzado para el test'),
        ):
            # No debe propagar — el error de la reubicación se traga.
            pick.write({'scheduled_date': dt_start_b})

        # Estado documentado tras el fallo, no solo "no revienta":
        # el picking SÍ tiene la fecha nueva (la escritura de bodega
        # no se tumba)...
        self.assertEqual(pick.scheduled_date, dt_start_b)
        # ...pero la línea de preparación se queda en la sesión VIEJA
        # (el savepoint revirtió la reubicación completa, no quedó a
        # medias)...
        line.invalidate_recordset()
        self.assertEqual(line.wizard_id.id, session_a.id)
        self.assertIn(line, session_a.line_ids)
        # ...y la base queda consistente con eso: el savepoint también
        # revirtió la CREACIÓN de la sesión nueva (pasa antes, dentro
        # del mismo bloque) — no debe quedar una sesión vacía para el
        # día nuevo como residuo del intento fallido.
        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        self.assertFalse(
            session_b,
            'El savepoint debe revertir también la sesión nueva creada a medias',
        )

        # DEF-01 (Tech Lead, 2026-10-29): el fallo no debe quedar solo
        # en el log técnico — nota visible en el chatter del picking,
        # con el estado real (desincronizado) documentado ahí. Se
        # verifica ACÁ, antes de cualquier otra escritura: una
        # escritura normal de otro campo (ver más abajo) agrega su
        # propio mensaje de tracking (body vacío) al chatter, que
        # quedaría por encima del nuestro si se mirara después.
        pick.invalidate_recordset()
        new_messages = pick.message_ids.sorted('id', reverse=True)[
            :len(pick.message_ids) - messages_before
        ]
        self.assertTrue(
            any('no se pudo actualizar' in (m.body or '') for m in new_messages),
            'Debe quedar una nota visible en el chatter del picking',
        )

        # La transacción debe seguir viva tras el savepoint — una
        # escritura normal después no debe fallar con "current
        # transaction is aborted".
        pick.write({'origin': 'post-fallo'})
        self.assertEqual(pick.origin, 'post-fallo')

    def test_relocation_serialization_failure_propagates_not_swallowed(self):
        """Corrección de Tech Lead (2026-10-30), mismo defecto que en
        _guapante_add_confirmed_order: un error transitorio de Postgres
        (SerializationFailure/LockNotAvailable/DeadlockDetected) debe
        propagarse tal cual para que Odoo reintente la petición
        completa — nunca quedar atrapado por el except Exception
        genérico de _guapante_relocate_picking."""
        order, pick = self._create_confirmed_order(self.day_a)
        self._load_session(self.day_a)
        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        with patch.object(
            type(self.env['guapante.preparation.day']),
            '_guapante_patch_summary',
            side_effect=pg_errors.SerializationFailure('simulado por test'),
        ):
            with self.assertRaises(pg_errors.SerializationFailure):
                pick.write({'scheduled_date': dt_start_b})

    def test_relocation_lock_for_update_covers_both_sessions_ascending(self):
        """Corrección BLOQUEANTE de Tech Lead (2026-10-30):
        _guapante_relocate_picking no tomaba ningún lock real a pesar
        de que su docstring lo daba por hecho — ahora bloquea origen
        Y destino en una sola consulta con ORDER BY id (para que dos
        reubicaciones cruzadas nunca se bloqueen en orden distinto)."""
        order, pick = self._create_confirmed_order(self.day_a)
        session_a = self._load_session(self.day_a)
        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)

        original_execute = type(self.env.cr).execute
        calls = []

        def _spy_execute(cr_self, query, params=None, *args, **kwargs):
            calls.append((query, params))
            return original_execute(cr_self, query, params, *args, **kwargs)

        with patch.object(type(self.env.cr), 'execute', _spy_execute):
            pick.write({'scheduled_date': dt_start_b})

        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        lock_calls = [
            (q, p) for q, p in calls
            if 'FOR UPDATE' in q and 'guapante_preparation_day' in q
        ]
        self.assertTrue(
            lock_calls, 'no se ejecutó ningún SELECT ... FOR UPDATE',
        )
        query, params = lock_calls[0]
        self.assertIn(
            'ORDER BY id', query,
            'sin ORDER BY, dos reubicaciones cruzadas podrían '
            'bloquear en orden distinto y causar un deadlock real',
        )
        ids_param = set(params[0]) if params else set()
        self.assertEqual(ids_param, {session_a.id, session_b.id})

    def test_relocation_recompacts_origin_flexible_boxes(self):
        """e3, ajuste 1 de Tech Lead (2026-10-30): la reubicación
        renumera TAMBIÉN el origen — las flexibles que quedan se
        recompactan al número que deja libre la orden que se fue; la
        fija de la sesión origen no se toca; el destino recibe su
        propio número correcto."""
        order_1, pick_1 = self._create_confirmed_order(self.day_a)
        order_2, _pick_2 = self._create_confirmed_order(self.day_a)
        order_3, _pick_3 = self._create_confirmed_order(self.day_a)
        session_a = self._load_session(self.day_a)

        self.assertEqual(order_1.daily_sequence, 1)
        self.assertEqual(order_2.daily_sequence, 2)
        self.assertEqual(order_3.daily_sequence, 3)

        line_2 = self._line_for(order_2)
        line_2.sudo().write({'is_done': True})  # Caja #2 ya pesada — FIJA.

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick_1.write({'scheduled_date': dt_start_b})  # order_1 se va.

        session_a.invalidate_recordset()
        order_1.invalidate_recordset()
        order_2.invalidate_recordset()
        order_3.invalidate_recordset()

        self.assertEqual(
            order_2.daily_sequence, 2, 'la fija del origen no se toca',
        )
        self.assertEqual(
            order_3.daily_sequence, 1,
            'la flexible que queda en el origen se recompacta al '
            'número que deja libre la que se fue',
        )
        self.assertEqual(
            order_1.daily_sequence, 1,
            'en el destino, order_1 es la única orden — le toca #1',
        )

    # ── DEF-01: pedido de varias líneas/productos no debe reventar ──

    def _create_confirmed_order_multi(self, day, products):
        """products: lista de product.product (se repite uno para
        probar el caso de producto duplicado dentro del mismo pedido)."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {'product_id': p.id, 'product_uom_qty': 1})
                for p in products
            ],
        })
        order.action_confirm()
        dt_start, _dt_end = _date_to_utc_range(self.env, day)
        pick = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal'
            and p.state not in ('done', 'cancel')
        )
        pick.scheduled_date = dt_start
        return order, pick

    def test_multiline_order_distinct_products_relocates_without_crashing(self):
        order, pick = self._create_confirmed_order_multi(
            self.day_a, [self.product, self.product_2, self.product_3],
        )
        session_a = self._load_session(self.day_a)
        lines = self._line_for(order)
        self.assertEqual(len(lines), 3)
        old_seq = order.daily_sequence
        self.assertTrue(old_seq > 0)

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.scheduled_date = dt_start_b  # no debe lanzar ValueError: Expected singleton

        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        lines.invalidate_recordset()
        order.invalidate_recordset()
        self.assertTrue(all(line.wizard_id.id == session_b.id for line in lines))
        self.assertNotIn(lines[0], session_a.line_ids)
        self.assertEqual(lines.mapped('daily_sequence'), [order.daily_sequence] * 3)

        for product in (self.product, self.product_2, self.product_3):
            summary_a = session_a.summary_ids.filtered(
                lambda s, p=product: s.product_id == p,
            )
            self.assertFalse(
                summary_a.exists(),
                'Cada summary viejo debe desaparecer (quedó en 0 órdenes)',
            )
            summary_b = session_b.summary_ids.filtered(
                lambda s, p=product: s.product_id == p,
            )
            self.assertEqual(summary_b.order_count, 1)

        note = session_b.message_ids.sorted('id', reverse=True)[0]
        self.assertIn(f'Caja #{order.daily_sequence}', note.body)

    def test_multiline_order_repeated_product_sums_into_one_summary(self):
        order, pick = self._create_confirmed_order_multi(
            self.day_a, [self.product, self.product],
        )
        session_a = self._load_session(self.day_a)
        lines = self._line_for(order)
        self.assertEqual(len(lines), 2)
        summary_a = session_a.summary_ids.filtered(
            lambda s: s.product_id == self.product,
        )
        self.assertEqual(summary_a.order_count, 2)

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.scheduled_date = dt_start_b

        summary_a.invalidate_recordset()
        self.assertFalse(summary_a.exists())
        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        summary_b = session_b.summary_ids.filtered(
            lambda s: s.product_id == self.product,
        )
        self.assertEqual(
            summary_b.order_count, 2,
            'Las 2 líneas del mismo producto deben sumar las 2, no colapsar en 1',
        )
        lines.invalidate_recordset()
        self.assertTrue(all(line.wizard_id.id == session_b.id for line in lines))

    def test_multiline_order_relocates_back_and_forth(self):
        order, pick = self._create_confirmed_order_multi(
            self.day_a, [self.product, self.product_2, self.product_3],
        )
        self._load_session(self.day_a)
        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.scheduled_date = dt_start_b  # ida

        dt_start_a, _ = _date_to_utc_range(self.env, self.day_a)
        pick.scheduled_date = dt_start_a  # vuelta — no debe lanzar ValueError

        session_a = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_a)], limit=1,
        )
        lines = self._line_for(order)
        self.assertTrue(all(line.wizard_id.id == session_a.id for line in lines))
        for product in (self.product, self.product_2, self.product_3):
            summary_a = session_a.summary_ids.filtered(
                lambda s, p=product: s.product_id == p,
            )
            self.assertEqual(
                summary_a.order_count, 1,
                'Después de ida y vuelta, el summary original debe quedar igual que al principio',
            )
