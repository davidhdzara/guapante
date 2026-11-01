# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
from unittest.mock import patch

import pytz
from psycopg2 import errors as pg_errors

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.tests.test_sale_order_auto_load import (
    TestSaleOrderAutoLoad,
)

CURRENT_SESSION_DATE_TARGET = (
    'odoo.addons.ist_preparation_day.models.preparation_day'
    '._current_session_date'
)


@tagged('post_install', '-at_install')
class TestPreparationDayCronRepair(TestSaleOrderAutoLoad):
    """Plan de carga automática, paso e4 (2026-10-30): cron de
    respaldo (_cron_repair_missing_orders) — red de seguridad para
    cuando e2/e3 fallan a mitad de camino, nunca el mecanismo
    principal. Hereda _confirm_order() (fecha fija, collision-free)
    de TestSaleOrderAutoLoad.
    """

    def _run_cron(self):
        self.env['guapante.preparation.day']._cron_repair_missing_orders()

    def _bogota_to_utc(self, day, hour, minute):
        bogota_tz = pytz.timezone('America/Bogota')
        return bogota_tz.localize(
            datetime.combine(day, time(hour, minute)),
        ).astimezone(pytz.utc).replace(tzinfo=None)

    def _run_cron_as_of(self, fake_today, hour=0, minute=10):
        """Corre el cron con _current_session_date() fijado a
        fake_today — las pruebas de la corrección (a) usan
        self.delivery_date (hoy+14, ya probado libre de colisión con
        datos reales por el resto de esta suite) como "hoy" simulado,
        para poder probar el rango hoy..hoy+N sin pisar sesiones
        reales de staging_dev.

        hour/minute (hora Bogotá, corrección de #4 2026-11-01):
        también fija fields.Datetime.now() a fake_today a esa hora,
        para poder probar la protección de "mañana" según
        _is_past_picking_switch_hour (que lee el reloj real, no
        _current_session_date) y la gracia de 30 min por write_date.
        Default 00:10 — antes de la hora de corte (21:00 default) —
        para no cambiar el comportamiento de las pruebas que no son
        sobre esto. Mismo patrón ya usado por _confirm_order_on_day
        en esta clase."""
        fixed_now = self._bogota_to_utc(fake_today, hour, minute)
        with patch(CURRENT_SESSION_DATE_TARGET, return_value=fake_today), \
             patch('odoo.fields.Datetime.now', return_value=fixed_now):
            self.env['guapante.preparation.day']._cron_repair_missing_orders()

    def _confirm_order_on_day(self, day, product=None, qty=1.0):
        """Variante de _confirm_order() con una fecha explícita en
        vez de self.delivery_date — para tener una SEGUNDA sesión
        independiente en los tests que necesitan dos a la vez."""
        product = product or self.product_weight
        order = self.env['sale.order'].create({
            'partner_id': self.child_partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
            })],
        })
        bogota_tz = pytz.timezone('America/Bogota')
        fixed_now = bogota_tz.localize(
            datetime.combine(day, time(0, 10)),
        ).astimezone(pytz.utc).replace(tzinfo=None)
        with patch('odoo.fields.Datetime.now', return_value=fixed_now):
            order.action_confirm()
        return order

    def test_cron_adds_missing_order_line_and_posts_notice(self):
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        self.assertEqual(len(Session.line_ids), 1)

        # Simula un disparador que falló a mitad de camino: la línea
        # nunca llegó a crearse.
        Session.line_ids.unlink()
        messages_before = len(Session.message_ids)

        self._run_cron()

        Session.invalidate_recordset()
        self.assertEqual(len(Session.line_ids), 1)
        self.assertEqual(Session.line_ids.sale_order_id, order)
        self.assertGreater(len(Session.message_ids), messages_before)
        self.assertTrue(
            any(
                'respaldo automático agregó' in (m or '')
                for m in Session.message_ids.mapped('body')
            )
        )

    def test_cron_second_run_does_not_duplicate(self):
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        Session.line_ids.unlink()

        self._run_cron()
        Session.invalidate_recordset()
        self.assertEqual(len(Session.line_ids), 1)

        self._run_cron()  # segunda corrida — nada que reparar
        Session.invalidate_recordset()
        self.assertEqual(len(Session.line_ids), 1)

    def test_cron_never_touches_done_session(self):
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        Session.line_ids.unlink()
        Session.action_mark_done()
        messages_before = len(Session.message_ids)

        self._run_cron()

        Session.invalidate_recordset()
        self.assertEqual(
            len(Session.line_ids), 0,
            'una sesión done nunca se repara, aunque le falte algo',
        )
        self.assertEqual(len(Session.message_ids), messages_before)

    def test_cron_no_notice_when_nothing_missing(self):
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        self.assertEqual(len(Session.line_ids), 1)  # e2 ya la agregó
        messages_before = len(Session.message_ids)

        self._run_cron()

        Session.invalidate_recordset()
        self.assertEqual(len(Session.line_ids), 1)
        self.assertEqual(
            len(Session.message_ids), messages_before,
            'sin nada faltante, el cron no debe dejar ninguna nota',
        )

    def test_cron_populates_new_empty_draft_session_via_action_load(self):
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        # Vuelve a dejarla como recién creada, sin autopoblar.
        Session.line_ids.unlink()
        Session.summary_ids.unlink()
        Session.sudo().write({'state': 'draft', 'date_start': False})

        self._run_cron()

        Session.invalidate_recordset()
        self.assertEqual(Session.state, 'loaded')
        self.assertEqual(len(Session.line_ids), 1)

    def test_cron_skips_draft_session_with_partial_lines(self):
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        # Queda 'draft' con una línea ya puesta — simula una carga a
        # medias manual, no la rama de sesión vacía.
        Session.sudo().write({'state': 'draft'})
        messages_before = len(Session.message_ids)

        self._run_cron()

        Session.invalidate_recordset()
        self.assertEqual(Session.state, 'draft')
        self.assertEqual(len(Session.line_ids), 1)
        self.assertEqual(len(Session.message_ids), messages_before)

    def test_cron_concurrency_error_in_one_session_does_not_abort_others(self):
        """Corrección de Tech Lead (2026-10-30): a diferencia de e2/
        e3, el cron corre en UNA transacción — un error de
        concurrencia en una sesión NO debe tumbar el trabajo ya
        reparado en las demás sesiones de la misma corrida."""
        order_a, date_a = self._confirm_order(
            product=self.product_weight, qty=5.0,
        )
        Session_a = self.env['guapante.preparation.day'].search(
            [('date', '=', date_a)], limit=1,
        )
        Session_a.line_ids.unlink()

        far_day = fields.Date.add(self.delivery_date, days=5)
        order_b = self._confirm_order_on_day(
            far_day, product=self.product_unit, qty=2.0,
        )
        Session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', far_day)], limit=1,
        )
        Session_b.line_ids.unlink()

        Model = type(self.env['guapante.preparation.day'])
        original_patch_summary = Model._guapante_patch_summary

        def _patched(self_model, session, line, add):
            if session.id == Session_a.id:
                raise pg_errors.SerializationFailure('simulado por test')
            return original_patch_summary(self_model, session, line, add)

        with patch.object(Model, '_guapante_patch_summary', _patched):
            self._run_cron()

        Session_a.invalidate_recordset()
        Session_b.invalidate_recordset()
        self.assertEqual(
            len(Session_a.line_ids), 0,
            'la sesión que chocó queda sin reparar en esta corrida',
        )
        self.assertEqual(
            len(Session_b.line_ids), 1,
            'la otra sesión SÍ debe repararse en la misma corrida',
        )

    def test_cron_draft_empty_session_without_orders_does_not_post_failure_note(self):
        """Corrección de Tech Lead (2026-10-30, bloqueante): una
        sesión draft sin líneas Y sin pedidos elegibles ese día (p.
        ej. quedó vacía tras una reubicación, o es una fecha futura
        sin pedidos aún) no es un fallo — action_load() lanzaría
        UserError por diseño si se llamara. El cron corre cada 10
        min: sin este corte dejaría una nota de fallo en el chatter
        para siempre."""
        # day = fake_today (HOY), a propósito, no una fecha futura
        # cualquiera: desde la corrección de rango de #4 (2026-11-01),
        # _run_cron_as_of también fija fields.Datetime.now() a
        # fake_today (para poder probar la hora de corte y la gracia
        # de 30 min) — eso deja el "ahora" de la prueba bien adelante
        # del "ahora" real en el que esta sesión se crea, así que la
        # gracia de 30 min NO la protegería (se vería "vieja" contra
        # un reloj ya adelantado). Solo "hoy" protege sin depender de
        # esa gracia — este test es sobre la nota de fallo, no sobre
        # el borrado, así que usa la fecha que no depende de ese
        # detalle.
        fake_today = self.delivery_date
        day = fake_today
        Session = self.env['guapante.preparation.day']._ensure_session_for_date(
            day,
        )
        self.assertEqual(Session.state, 'draft')
        self.assertEqual(len(Session.line_ids), 0)
        messages_before = len(Session.message_ids)

        for _ in range(3):
            self._run_cron_as_of(fake_today)

        Session.invalidate_recordset()
        self.assertEqual(Session.state, 'draft')
        self.assertEqual(len(Session.line_ids), 0)
        self.assertEqual(
            len(Session.message_ids), messages_before,
            'una sesión draft sin pedidos elegibles no debe generar '
            'ninguna nota de fallo en el chatter, ni siquiera tras '
            'varias corridas',
        )

    def test_cron_repeated_failure_posts_note_only_once(self):
        """Corrección de Tech Lead (2026-10-30): dos corridas fallando
        seguidas (cada 10 min) deben dejar UNA sola nota de fallo en
        el chatter, no una por corrida — el log.exception sí se deja
        en cada corrida, solo la nota visible se deduplica."""
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        Session.line_ids.unlink()

        Model = type(self.env['guapante.preparation.day'])

        def _raise_value_error(self_model, session, line, add):
            raise ValueError('boom cron test repetido')

        with patch.object(Model, '_guapante_patch_summary', _raise_value_error):
            self._run_cron()
            self._run_cron()

        Session.invalidate_recordset()
        failure_notes = [
            m for m in Session.message_ids.mapped('body')
            if 'falló' in (m or '')
        ]
        self.assertEqual(
            len(failure_notes), 1,
            'dos corridas fallando seguidas deben dejar una sola '
            'nota, no una por corrida',
        )

    def test_cron_other_exception_logs_and_posts_notice_without_crashing(self):
        order, date_val = self._confirm_order(qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', date_val)], limit=1,
        )
        Session.line_ids.unlink()
        messages_before = len(Session.message_ids)

        Model = type(self.env['guapante.preparation.day'])

        def _raise_value_error(self_model, session, line, add):
            raise ValueError('boom cron test')

        with patch.object(Model, '_guapante_patch_summary', _raise_value_error):
            self._run_cron()  # no debe propagar

        Session.invalidate_recordset()
        self.assertEqual(len(Session.line_ids), 0)
        self.assertGreater(len(Session.message_ids), messages_before)
        self.assertTrue(
            any(
                'falló' in (m or '')
                for m in Session.message_ids.mapped('body')
            )
        )

    # ------------------------------------------------------------------
    # Corrección (a), Tech Lead 2026-10-31: el cron también CREA la
    # sesión que falte por completo, hoy..hoy+N, si ya hay pedidos
    # elegibles (caso real: pedidos confirmados antes de instalar el
    # módulo). Usa self.delivery_date (hoy+14) como "hoy" simulado via
    # _run_cron_as_of — rango libre de colisión ya probado por el
    # resto de la suite.
    # ------------------------------------------------------------------

    def test_cron_creates_missing_session_and_loads_orders(self):
        fake_today = self.delivery_date
        order = self._confirm_order_on_day(fake_today, qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', fake_today)], limit=1,
        )
        self.assertTrue(Session)
        Session.unlink()
        self.assertFalse(
            self.env['guapante.preparation.day'].search(
                [('date', '=', fake_today)], limit=1,
            )
        )

        self._run_cron_as_of(fake_today)

        NewSession = self.env['guapante.preparation.day'].search(
            [('date', '=', fake_today)], limit=1,
        )
        self.assertTrue(NewSession, 'debe crear la sesión que faltaba')
        self.assertEqual(NewSession.state, 'loaded')
        Line = NewSession.line_ids.filtered(
            lambda l: l.sale_order_id == order,
        )
        self.assertEqual(len(Line), 1)

    def test_cron_second_run_does_not_duplicate_created_session(self):
        fake_today = self.delivery_date
        self._confirm_order_on_day(fake_today, qty=5.0)
        self.env['guapante.preparation.day'].search(
            [('date', '=', fake_today)],
        ).unlink()

        self._run_cron_as_of(fake_today)
        self.assertEqual(
            len(self.env['guapante.preparation.day'].search(
                [('date', '=', fake_today)],
            )),
            1,
        )

        self._run_cron_as_of(fake_today)  # segunda corrida
        self.assertEqual(
            len(self.env['guapante.preparation.day'].search(
                [('date', '=', fake_today)],
            )),
            1,
            'la segunda corrida no debe duplicar la sesión creada',
        )

    def test_cron_creates_nothing_when_no_eligible_orders_in_range(self):
        fake_today = self.delivery_date
        before = self.env['guapante.preparation.day'].search([
            ('date', '>=', fake_today),
            ('date', '<=', fake_today + timedelta(days=7)),
        ])
        self.assertFalse(before, 'precondición: nada en el rango todavía')

        self._run_cron_as_of(fake_today)

        after = self.env['guapante.preparation.day'].search([
            ('date', '>=', fake_today),
            ('date', '<=', fake_today + timedelta(days=7)),
        ])
        self.assertFalse(
            after, 'sin pedidos elegibles no debe crear ninguna sesión',
        )

    def test_cron_skips_creating_session_when_today_already_done(self):
        """Condición 2 de Tech Lead: hoy con sesión 'done' + pedidos
        elegibles (el picking de la orden ya confirmada, sin validar
        todavía) → no debe crear nada ni dejar ninguna nota — el
        chequeo "¿ya existe ALGUNA sesión para esta fecha?" corta
        antes de mirar los pedidos."""
        fake_today = self.delivery_date
        self._confirm_order_on_day(fake_today, qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', fake_today)], limit=1,
        )
        Session.line_ids.unlink()
        Session.action_mark_done()
        messages_before = len(Session.message_ids)

        self._run_cron_as_of(fake_today)

        Session.invalidate_recordset()
        self.assertEqual(Session.state, 'done')
        self.assertEqual(len(Session.line_ids), 0)
        self.assertEqual(
            len(Session.message_ids), messages_before,
            'una sesión done de hoy nunca se toca ni genera ruido',
        )

    def test_cron_does_not_create_session_for_past_dates(self):
        fake_today = self.delivery_date
        past_day = fake_today - timedelta(days=1)
        self._confirm_order_on_day(past_day, qty=5.0)
        self.env['guapante.preparation.day'].search(
            [('date', '=', past_day)],
        ).unlink()
        self.assertFalse(
            self.env['guapante.preparation.day'].search(
                [('date', '=', past_day)], limit=1,
            )
        )

        self._run_cron_as_of(fake_today)

        self.assertFalse(
            self.env['guapante.preparation.day'].search(
                [('date', '=', past_day)], limit=1,
            ),
            'el cron nunca debe crear sesión para una fecha pasada, '
            'aunque haya pedidos elegibles y no exista sesión',
        )

    def test_cron_failure_creating_one_date_does_not_block_others(self):
        fake_today = self.delivery_date
        day_a = fake_today
        day_b = fake_today + timedelta(days=3)
        self._confirm_order_on_day(
            day_a, product=self.product_weight, qty=5.0,
        )
        self._confirm_order_on_day(
            day_b, product=self.product_unit, qty=2.0,
        )
        self.env['guapante.preparation.day'].search(
            [('date', '=', day_a)],
        ).unlink()
        self.env['guapante.preparation.day'].search(
            [('date', '=', day_b)],
        ).unlink()

        Model = type(self.env['guapante.preparation.day'])
        original_ensure = Model._ensure_session_for_date

        def _patched_ensure(self_model, date_val):
            if date_val == day_a:
                raise ValueError('boom creación forzada en día A')
            return original_ensure(self_model, date_val)

        with patch.object(Model, '_ensure_session_for_date', _patched_ensure):
            self._run_cron_as_of(fake_today)

        SessionA = self.env['guapante.preparation.day'].search(
            [('date', '=', day_a)], limit=1,
        )
        SessionB = self.env['guapante.preparation.day'].search(
            [('date', '=', day_b)], limit=1,
        )
        self.assertFalse(
            SessionA, 'la fecha que falló no debe quedar a medias',
        )
        self.assertTrue(
            SessionB, 'la otra fecha sí debe crearse en la misma corrida',
        )
        self.assertEqual(SessionB.state, 'loaded')

    def test_cron_created_session_assigns_daily_sequence_1_to_n(self):
        """Condición 3 de Tech Lead: tras crear+cargar vía el cron,
        3 pedidos sin número (daily_sequence=0) reciben 1..N en el
        orden de sale_id — ya lo hace _assign_daily_sequences dentro
        de action_load(), esta prueba confirma que SÍ se dispara por
        este camino nuevo."""
        fake_today = self.delivery_date
        day = fake_today + timedelta(days=2)
        orders = [
            self._confirm_order_on_day(
                day, product=self.product_weight, qty=float(i + 1),
            )
            for i in range(3)
        ]
        self.env['guapante.preparation.day'].search(
            [('date', '=', day)],
        ).unlink()
        for order in orders:
            order.daily_sequence = 0

        self._run_cron_as_of(fake_today)

        NewSession = self.env['guapante.preparation.day'].search(
            [('date', '=', day)], limit=1,
        )
        self.assertTrue(NewSession)
        self.assertEqual(NewSession.state, 'loaded')
        for order in orders:
            order.invalidate_recordset(['daily_sequence'])
        self.assertEqual(
            [o.daily_sequence for o in orders], [1, 2, 3],
            'numeración 1..N en el orden de sale_id (orden de creación)',
        )

    # ------------------------------------------------------------------
    # #4 (David/Tech Lead, 2026-10-31, caso real sesión 218; corrección
    # de rango 2026-11-01, caso real: la vacía del 2-nov no desaparecía
    # y reaparecía al llegar un pedido nuevo — justo lo que #4 quería
    # evitar). El cron también BORRA una sesión draft/loaded vacía (sin
    # líneas, sin claims, sin historial de pesaje, sin pedidos
    # elegibles pendientes) en CUALQUIER fecha, salvo: hoy; mañana
    # SOLO si ya pasó la hora de corte del tablet (#12); o con
    # write_date de menos de 30 min (gracia contra carreras). El rango
    # hoy..hoy+days_ahead de la fase de creación de arriba YA NO
    # protege del borrado — un pedido nuevo para una fecha sin sesión
    # la recrea por e2 (_ensure_session_for_date), así que borrar una
    # vacía fuera de hoy/mañana nunca es definitivo.
    # ------------------------------------------------------------------

    def _empty_session_on(self, day, write_date=None):
        """write_date (corrección de #4, 2026-11-01): opcional, para
        las pruebas de la gracia de 30 minutos — escribe write_date
        directo por SQL (la ORM no deja escribirlo por write()). Sin
        este parámetro, la sesión queda con su write_date real de
        creación — en las pruebas que simulan un "hoy" muy adelante
        en el futuro (self.delivery_date, +14 días) eso ya es, de
        sobra, más viejo que la gracia de 30 min medida contra el
        reloj fijado de la prueba, así que no hace falta forzarlo."""
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', day)], limit=1,
        )
        if not Session:
            Session = self.env['guapante.preparation.day'].create(
                {'date': day},
            )
        if write_date is not None:
            self.env.cr.execute(
                'UPDATE guapante_preparation_day SET write_date = %s '
                'WHERE id = %s', (write_date, Session.id),
            )
            Session.invalidate_recordset(['write_date'])
        return Session

    def test_cron_deletes_empty_session_tomorrow_before_switch_hour(self):
        """Antes de la hora de corte del tablet (#12), mañana no es
        terreno protegido todavía — una vacía sí se borra."""
        fake_today = self.delivery_date
        tomorrow = fake_today + timedelta(days=1)
        Session = self._empty_session_on(tomorrow)
        session_id = Session.id

        self._run_cron_as_of(fake_today, hour=10, minute=0)

        self.assertFalse(
            self.env['guapante.preparation.day'].browse(
                session_id,
            ).exists(),
            'antes de la hora de corte, una sesión vacía de mañana '
            'sí se borra — el tablet todavía no puede estar entrando '
            'ahí',
        )

    def test_cron_does_not_delete_empty_session_tomorrow_after_switch_hour(self):
        """Pasada la hora de corte del tablet (#12), mañana queda
        protegida — el tablet puede estar entrando ahí mismo."""
        fake_today = self.delivery_date
        tomorrow = fake_today + timedelta(days=1)
        Session = self._empty_session_on(tomorrow)

        self._run_cron_as_of(fake_today, hour=22, minute=0)

        self.assertTrue(
            Session.exists(),
            'pasada la hora de corte, la sesión vacía de mañana no '
            'se borra — el tablet puede estar entrando ahí',
        )

    def test_cron_does_not_delete_empty_session_today(self):
        fake_today = self.delivery_date
        Session = self._empty_session_on(fake_today)

        self._run_cron_as_of(fake_today, hour=22, minute=0)

        self.assertTrue(
            Session.exists(),
            'la sesión de hoy (la jornada en curso) nunca se borra, '
            'esté vacía o no, pase o no la hora de corte',
        )

    def test_cron_does_not_delete_fresh_empty_session_within_grace_window(self):
        """Gracia de 30 min (corrección de #4, 2026-11-01): una sesión
        recién tocada (por el tablet o por e2, todavía sin su primera
        línea) no se borra aunque su fecha no sea hoy ni mañana —
        evita una carrera entre la creación y este mismo cron."""
        fake_today = self.delivery_date
        day = fake_today + timedelta(days=5)
        fixed_now = self._bogota_to_utc(fake_today, 10, 0)
        Session = self._empty_session_on(
            day, write_date=fixed_now - timedelta(minutes=5),
        )

        self._run_cron_as_of(fake_today, hour=10, minute=0)

        self.assertTrue(
            Session.exists(),
            'una sesión tocada hace solo 5 minutos no se borra, '
            'aunque su fecha no sea hoy ni mañana',
        )

    def test_cron_deletes_empty_session_outside_grace_window(self):
        """Misma fecha y hora que la prueba de arriba, pero con
        write_date de 31 minutos atrás (fuera de la gracia) — control
        de que la gracia es lo único que protegía a la de arriba."""
        fake_today = self.delivery_date
        day = fake_today + timedelta(days=5)
        fixed_now = self._bogota_to_utc(fake_today, 10, 0)
        Session = self._empty_session_on(
            day, write_date=fixed_now - timedelta(minutes=31),
        )
        session_id = Session.id

        self._run_cron_as_of(fake_today, hour=10, minute=0)

        self.assertFalse(
            self.env['guapante.preparation.day'].browse(
                session_id,
            ).exists(),
        )

    def test_cron_deletes_empty_session_past_the_old_range(self):
        fake_today = self.delivery_date
        far_day = fake_today + timedelta(days=30)
        Session = self._empty_session_on(
            far_day,
            write_date=self._bogota_to_utc(fake_today, 10, 0) - timedelta(minutes=31),
        )
        session_id = Session.id

        self._run_cron_as_of(fake_today, hour=10, minute=0)

        self.assertFalse(
            self.env['guapante.preparation.day'].browse(
                session_id,
            ).exists(),
            'una sesión vacía muy lejos en el futuro sí se borra — '
            'el rango de creación ya no protege del borrado',
        )

    def test_cron_deletes_empty_session_within_the_old_range(self):
        """Antes de la corrección de rango (2026-11-01) esta fecha
        (hoy+3, dentro de hoy..hoy+days_ahead) quedaba protegida del
        borrado — ya no: solo hoy/mañana/gracia protegen."""
        fake_today = self.delivery_date
        day = fake_today + timedelta(days=3)
        Session = self._empty_session_on(
            day,
            write_date=self._bogota_to_utc(fake_today, 10, 0) - timedelta(minutes=31),
        )
        session_id = Session.id

        self._run_cron_as_of(fake_today, hour=10, minute=0)

        self.assertFalse(
            self.env['guapante.preparation.day'].browse(
                session_id,
            ).exists(),
        )

    def test_cron_deletes_empty_session_in_the_past(self):
        fake_today = self.delivery_date
        past_day = fake_today - timedelta(days=1)
        Session = self._empty_session_on(past_day)
        session_id = Session.id

        self._run_cron_as_of(fake_today)

        self.assertFalse(
            self.env['guapante.preparation.day'].browse(
                session_id,
            ).exists(),
            'una sesión vacía de ayer sí se borra',
        )

    def test_cron_does_not_delete_and_recreate_tomorrow_after_switch_hour(self):
        """Pasada la hora de corte, mañana queda protegida de forma
        estable en corridas sucesivas — nunca se borra y recrea en
        ciclo (lo que quemaría numeración de PK/PICK y le cambiaría
        el id cada vez)."""
        fake_today = self.delivery_date
        tomorrow = fake_today + timedelta(days=1)
        Session = self._empty_session_on(tomorrow)
        session_id = Session.id

        for _ in range(3):
            self._run_cron_as_of(fake_today, hour=22, minute=0)

        self.assertEqual(
            self.env['guapante.preparation.day'].search(
                [('date', '=', tomorrow)],
            ).id,
            session_id,
            'la sesión vacía de mañana, protegida por la hora de '
            'corte, debe seguir siendo la misma en corridas '
            'sucesivas, no un id nuevo cada vez',
        )

    def test_deleted_tomorrow_session_is_recreated_by_new_order_e2(self):
        """Tech Lead/David, 2026-11-01: borrada la sesión vacía de
        mañana (antes de la hora de corte), un pedido nuevo para esa
        fecha la recrea por e2 (_ensure_session_for_date) y entra en
        ella con normalidad — el borrado nunca es definitivo."""
        fake_today = self.delivery_date
        tomorrow = fake_today + timedelta(days=1)
        Session = self._empty_session_on(tomorrow)
        session_id = Session.id

        self._run_cron_as_of(fake_today, hour=10, minute=0)
        self.assertFalse(
            self.env['guapante.preparation.day'].browse(
                session_id,
            ).exists(),
            'precondición: la sesión vacía de mañana se borró',
        )

        order = self._confirm_order_on_day(tomorrow, qty=4.0)

        NewSession = self.env['guapante.preparation.day'].search(
            [('date', '=', tomorrow)], limit=1,
        )
        self.assertTrue(
            NewSession,
            'un pedido nuevo para esa fecha debe recrear la sesión',
        )
        self.assertNotEqual(
            NewSession.id, session_id,
            'es una sesión NUEVA (la vieja se borró de verdad)',
        )
        Line = NewSession.line_ids.filtered(
            lambda l: l.sale_order_id == order,
        )
        self.assertTrue(
            Line, 'la línea del pedido nuevo debe entrar en la '
            'sesión recreada',
        )

    def test_cron_never_deletes_done_session_even_if_empty(self):
        fake_today = self.delivery_date
        far_day = fake_today + timedelta(days=30)
        Session = self._empty_session_on(far_day)
        Session.action_mark_done()
        session_id = Session.id

        self._run_cron_as_of(fake_today)

        self.assertTrue(
            self.env['guapante.preparation.day'].browse(
                session_id,
            ).exists(),
            'una sesión done nunca se borra, aunque esté vacía y '
            'fuera del rango',
        )

    def test_cron_never_deletes_session_with_lines_even_outside_range(self):
        fake_today = self.delivery_date
        far_day = fake_today + timedelta(days=30)
        self._confirm_order_on_day(far_day, qty=5.0)
        Session = self.env['guapante.preparation.day'].search(
            [('date', '=', far_day)], limit=1,
        )
        self.assertTrue(Session.line_ids)

        self._run_cron_as_of(fake_today)

        self.assertTrue(Session.exists())
        self.assertEqual(len(Session.line_ids), 1)

    def test_cron_never_deletes_session_with_weighing_history(self):
        fake_today = self.delivery_date
        far_day = fake_today + timedelta(days=30)
        Session = self._empty_session_on(far_day)
        self.env['guapante.picking.log'].create({'wizard_id': Session.id})
        session_id = Session.id

        self._run_cron_as_of(fake_today)

        self.assertTrue(
            self.env['guapante.preparation.day'].browse(
                session_id,
            ).exists(),
            'historial de pesaje (guapante.picking.log) impide el '
            'borrado aunque hoy no tenga líneas',
        )

    def test_cron_cleanup_not_starved_by_many_old_sessions_with_lines(self):
        """Tech Lead, tras revisar 75439bc: el dominio original de
        EmptySessions no filtraba por line_ids — en staging_main/
        producción hay muchas sesiones 'loaded' pasadas CON líneas
        (ej. la 217, 210-216), que llenaban el tope de sesiones de la
        corrida antes de llegar a evaluar las vacías viejas de
        verdad, dejando la limpieza sin efecto en la práctica. Fuerza
        un tope bajo (2) y crea 3 sesiones pasadas CON líneas más una
        vacía — la vacía debe borrarse igual en la misma corrida."""
        fake_today = self.delivery_date
        self.env['ir.config_parameter'].sudo().set_param(
            'ist_preparation_day.cron_repair_max_sessions', '2',
        )
        for offset in (10, 9, 8):
            day = fake_today - timedelta(days=offset)
            self._confirm_order_on_day(day, qty=1.0)

        empty_day = fake_today - timedelta(days=1)
        EmptySession = self._empty_session_on(empty_day)
        empty_session_id = EmptySession.id

        self._run_cron_as_of(fake_today)

        self.assertFalse(
            self.env['guapante.preparation.day'].browse(
                empty_session_id,
            ).exists(),
            'la sesión vacía debe borrarse aunque existan más '
            'sesiones viejas CON líneas que el tope de la corrida',
        )
