# -*- coding: utf-8 -*-
"""Tests de la Regla de la jornada (David, 2026-10-29): la sesión de
la fecha D son los PICK cuyo scheduled_date cae en el día calendario D
(hora Bogotá), sin corte horario, y mover un PICK pendiente entre días
reubica su línea de preparación de forma incremental.

Cubre el plan aprobado por Tech Lead (2026-10-29) sobre el hallazgo de
Caja #0 / reubicación — ver reporte en el hilo de sesiones.
"""
from unittest.mock import patch

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

    def test_moving_never_loaded_picking_creates_draft_session(self):
        order, pick = self._create_confirmed_order(self.day_a)
        # Nunca se llama action_load() para day_a.
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
        self._load_session(self.day_a)

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        with patch.object(
            type(self.env['guapante.preparation.day']), '_guapante_patch_summary',
            side_effect=Exception('fallo forzado para el test'),
        ):
            # No debe propagar — el error de la reubicación se traga.
            pick.write({'scheduled_date': dt_start_b})

        self.assertEqual(pick.scheduled_date, dt_start_b)
        # La transacción debe seguir viva tras el savepoint — una
        # escritura normal después no debe fallar con "current
        # transaction is aborted".
        pick.write({'origin': 'post-fallo'})
        self.assertEqual(pick.origin, 'post-fallo')
