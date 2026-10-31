# -*- coding: utf-8 -*-
from datetime import datetime, time
from unittest.mock import patch

import pytz
from psycopg2 import errors as pg_errors

from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _utc_datetime_to_session_date,
)
from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)

ADD_LINES_TARGET = (
    'odoo.addons.ist_preparation_day.models.preparation_day'
    '.PreparationDay._guapante_add_order_lines'
)
ACTION_LOAD_TARGET = (
    'odoo.addons.ist_preparation_day.models.preparation_day'
    '.PreparationDay.action_load'
)
ENSURE_SESSION_TARGET = (
    'odoo.addons.ist_preparation_day.models.preparation_day'
    '.PreparationDay._ensure_session_for_date'
)


@tagged('post_install', '-at_install')
class TestSaleOrderAutoLoad(TestPreparationDay):
    """Plan de carga automática, paso e2 (2026-10-29): al confirmar una
    orden, su línea entra sola a la sesión de Preparación del Día de la
    fecha de su PICK — sin pasar por el botón "Actualizar pedidos".

    A propósito NO usa _create_confirmed_order() (que fuerza
    picking.scheduled_date a self.delivery_date DESPUÉS de confirmar,
    lo que dispara la reubicación ya existente — otro camino, no e2).
    Confirma directo, pero fijando `fields.Datetime.now()` (que lee
    theme_guapante.action_confirm para el corte 00:30) a las 00:10 hora
    Bogotá de self.delivery_date — el mismo día +14 que ya usa el resto
    de la suite "para evitar colisiones" (ver setUpClass de
    TestPreparationDay). Sin esto, la fecha "natural" sería HOY, que en
    este staging real puede tener una sesión YA CERRADA de verdad
    (pasó: 2026-10-30 ya existía como 'done' en la base real y tumbaba
    estos tests) — exactamente el mismo tipo de colisión con datos
    reales que ya se corrigió una vez en este proyecto (punto 0b).
    """

    def _confirm_order(self, product=None, qty=5.0, partner=None):
        product = product or self.product_weight
        partner = partner or self.child_partner
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
            })],
        })
        bogota_tz = pytz.timezone('America/Bogota')
        fixed_now = bogota_tz.localize(
            datetime.combine(self.delivery_date, time(0, 10)),
        ).astimezone(pytz.utc).replace(tzinfo=None)
        with patch('odoo.fields.Datetime.now', return_value=fixed_now):
            order.action_confirm()
        Picking = order.picking_ids.filtered(
            lambda p: (
                p.picking_type_code == 'internal'
                and p.state not in ('done', 'cancel')
            )
        )[:1]
        date_val = _utc_datetime_to_session_date(
            self.env, Picking.scheduled_date,
        )
        return order, date_val

    def test_action_confirm_creates_and_populates_new_session(self):
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        self.assertTrue(Session)
        self.assertEqual(Session.state, 'loaded')
        self.assertTrue(Session.date_start)
        Line = Session.line_ids.filtered(lambda l: l.sale_order_id == order)
        self.assertEqual(len(Line), 1)
        self.assertEqual(Line.estimated_kg, 5.0)
        Summary = Session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        self.assertEqual(len(Summary), 1)

    def test_action_confirm_incremental_add_to_already_loaded_session(self):
        order_a, date_val = self._confirm_order(
            product=self.product_weight, qty=5.0,
        )
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        self.assertEqual(Session.state, 'loaded')
        self.assertEqual(len(Session.line_ids), 1)

        order_b, date_b = self._confirm_order(
            product=self.product_unit, qty=3.0,
        )
        self.assertEqual(
            date_b, date_val,
            'ambas órdenes deben caer en la misma fecha natural de '
            'corte para ejercitar el alta incremental, no la creación',
        )

        LineB = Session.line_ids.filtered(lambda l: l.sale_order_id == order_b)
        self.assertEqual(len(LineB), 1)
        self.assertEqual(len(Session.line_ids), 2)
        SummaryUnit = Session.summary_ids.filtered(
            lambda s: s.product_id == self.product_unit
        )
        self.assertEqual(len(SummaryUnit), 1)
        self.assertEqual(SummaryUnit.order_count, 1)

    def test_action_confirm_other_products_untouched_by_incremental_add(self):
        """Condición 1 de Tech Lead: el alta incremental no puede tocar
        summaries/claims de otros productos ya en curso en la sesión."""
        order_a, date_val = self._confirm_order(
            product=self.product_weight, qty=5.0,
        )
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        LineA = Session.line_ids.filtered(lambda l: l.sale_order_id == order_a)
        SummaryA = Session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        summary_a_snapshot = (
            SummaryA.total_estimated_kg, SummaryA.order_count,
        )

        self._confirm_order(product=self.product_unit, qty=3.0)

        SummaryA_after = Session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        self.assertEqual(
            (SummaryA_after.total_estimated_kg, SummaryA_after.order_count),
            summary_a_snapshot,
        )
        self.assertEqual(LineA.estimated_kg, 5.0)

    def test_action_confirm_second_confirm_does_not_duplicate_line(self):
        """Condición 4 de Tech Lead: "confirmar dos veces la misma orden
        no duplica". Odoo base ya bloquea re-llamar action_confirm()
        sobre una orden en 'sale' (UserError "Some orders are not in a
        state requiring confirmation") — no es un camino real. La
        idempotencia que importa es la del propio gancho, por si algo
        externo llega a invocarlo dos veces sobre la misma orden (p.ej.
        dos pickings del mismo pedido resolviendo la misma fecha)."""
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        self.assertEqual(len(Session.line_ids), 1)
        self.env['guapante.preparation.day']._guapante_add_confirmed_order(
            date_val, order,
        )
        self.assertEqual(len(Session.line_ids), 1)

    def test_two_orders_confirmed_back_to_back_on_new_session_no_duplicate_lines(self):
        """(b) de la condición de lock de Tech Lead: dos órdenes
        confirmadas una tras otra sobre una fecha nueva no pueden dejar
        líneas duplicadas por sale_line_id."""
        order_a, date_val = self._confirm_order(
            product=self.product_weight, qty=5.0,
        )
        order_b, date_b = self._confirm_order(
            product=self.product_unit, qty=3.0,
        )
        self.assertEqual(date_b, date_val)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        sale_line_ids = Session.line_ids.mapped('sale_line_id').ids
        self.assertEqual(len(sale_line_ids), len(set(sale_line_ids)))
        self.assertEqual(len(Session.line_ids), 2)
        self.assertEqual(
            set(Session.line_ids.mapped('sale_order_id')),
            {order_a, order_b},
        )

    def test_lock_for_update_executed_when_populating_new_session(self):
        """(a) de la condición de lock de Tech Lead: el SELECT ... FOR
        UPDATE sobre la fila de la sesión se ejecuta de verdad."""
        original_execute = type(self.env.cr).execute
        queries = []

        def _spy_execute(cr_self, query, *args, **kwargs):
            queries.append(query)
            return original_execute(cr_self, query, *args, **kwargs)

        with patch.object(type(self.env.cr), 'execute', _spy_execute):
            self._confirm_order(qty=5.0)

        self.assertTrue(
            any(
                'FOR UPDATE' in q and 'guapante_preparation_day' in q
                for q in queries
            ),
            'no se ejecutó el SELECT ... FOR UPDATE esperado sobre '
            'guapante_preparation_day',
        )

    def test_action_confirm_closed_session_posts_notice_without_adding(self):
        order_a, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        Session.action_mark_done()
        self.assertEqual(Session.state, 'done')

        order_b, date_b = self._confirm_order(
            product=self.product_unit, qty=2.0,
        )
        self.assertEqual(date_b, date_val)
        self.assertEqual(
            len(Session.line_ids.filtered(
                lambda l: l.sale_order_id == order_b
            )),
            0,
        )
        order_messages = order_b.message_ids.mapped('body')
        self.assertTrue(
            any('no se agregó' in (m or '') for m in order_messages)
        )
        session_messages = Session.message_ids.mapped('body')
        self.assertTrue(
            any('no se agregó' in (m or '') for m in session_messages)
        )

    def test_action_confirm_survives_exception_in_incremental_add(self):
        """Condición CRÍTICA de Tech Lead: confirmar una venta nunca
        puede fallar por Preparación, ni siquiera si el helper del alta
        incremental explota a mitad de camino. ValueError a propósito
        (no uno de _PG_CONCURRENCY_ERRORS) — este SÍ debe quedar
        atrapado, a diferencia del test de SerializationFailure de
        abajo."""
        self._confirm_order(qty=5.0)
        with patch(ADD_LINES_TARGET, side_effect=ValueError('boom e2 test')):
            order_b, _date_b = self._confirm_order(
                product=self.product_unit, qty=1.0,
            )
        self.assertEqual(order_b.state, 'sale')
        messages = order_b.message_ids.mapped('body')
        self.assertTrue(
            any('no se pudo agregar' in (m or '') for m in messages)
        )

    def test_action_confirm_survives_exception_populating_new_session(self):
        """Mismo chequeo crítico, pero para la rama de autopoblación
        completa de una sesión recién creada (self.action_load())."""
        with patch(ACTION_LOAD_TARGET, side_effect=ValueError('boom e2 test')):
            order, _date_val = self._confirm_order(qty=5.0)
        self.assertEqual(order.state, 'sale')
        messages = order.message_ids.mapped('body')
        self.assertTrue(
            any('no se pudo agregar' in (m or '') for m in messages)
        )

    def test_action_confirm_survives_exception_in_ensure_session(self):
        """Mismo chequeo crítico, pero para la propia resolución/
        creación de la sesión (_ensure_session_for_date), que ahora
        vive DENTRO del savepoint de _guapante_add_confirmed_order."""
        with patch(
            ENSURE_SESSION_TARGET, side_effect=ValueError('boom e2 test'),
        ):
            order, _date_val = self._confirm_order(qty=5.0)
        self.assertEqual(order.state, 'sale')
        messages = order.message_ids.mapped('body')
        self.assertTrue(
            any('no se pudo agregar' in (m or '') for m in messages)
        )

    def test_serialization_failure_propagates_not_swallowed(self):
        """Corrección de Tech Lead (2026-10-30): el propio diseño del
        lock depende de que Odoo VEA el error de serialización y
        reintente la petición completa — si _guapante_add_confirmed_order
        lo tragara con su except Exception genérico, el reintento nunca
        pasaría y la orden quedaría confirmada sin su línea. Simula el
        SELECT ... FOR UPDATE lanzando ese error específico y verifica
        que se propaga tal cual hasta el llamador, sin ser atrapado."""
        order, date_val = self._confirm_order(qty=5.0)
        original_execute = type(self.env.cr).execute

        def _raise_on_lock(cr_self, query, *args, **kwargs):
            if 'FOR UPDATE' in query and 'guapante_preparation_day' in query:
                raise pg_errors.SerializationFailure('simulado por test')
            return original_execute(cr_self, query, *args, **kwargs)

        with patch.object(type(self.env.cr), 'execute', _raise_on_lock):
            with self.assertRaises(pg_errors.SerializationFailure):
                self.env[
                    'guapante.preparation.day'
                ]._guapante_add_confirmed_order(date_val, order)
