# -*- coding: utf-8 -*-
from datetime import datetime, time
from unittest.mock import patch

import pytz
from psycopg2 import errors as pg_errors

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.tests.test_sale_order_auto_load import (
    TestSaleOrderAutoLoad,
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
        far_day = fields.Date.add(self.delivery_date, days=30)
        Session = self.env['guapante.preparation.day']._ensure_session_for_date(
            far_day,
        )
        self.assertEqual(Session.state, 'draft')
        self.assertEqual(len(Session.line_ids), 0)
        messages_before = len(Session.message_ids)

        for _ in range(3):
            self._run_cron()

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
