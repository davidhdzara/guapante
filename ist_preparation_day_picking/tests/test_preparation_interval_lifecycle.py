# -*- coding: utf-8 -*-
from datetime import datetime
from unittest.mock import MagicMock, patch

from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.controllers.preparation_day_identification_controller import (
    PreparationDayIdentificationController,
)

from .test_preparation_day_product_claim import TestPreparationDayProductClaim

REQUEST_PATCH_TARGET_CLAIM = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_product_claim.request'
)
REQUEST_PATCH_TARGET_LINE = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_line.request'
)
REQUEST_PATCH_TARGET_PARENT = (
    'odoo.addons.ist_preparation_day.models.preparation_day.request'
)
IDENTIFICATION_REQUEST_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day.controllers'
    '.preparation_day_identification_controller.request'
)


@tagged('post_install', '-at_install')
class TestPreparationIntervalLifecycle(TestPreparationDayProductClaim):
    """Fase 2, commit 2/7 (Tech Lead, 2026-11-04) — apertura/cierre real
    de guapante.preparation.interval a través de los mismos puntos del
    servidor que ya usan Asignarme/Retomar/Detener/Liberar/Terminar/
    Cerrar sesión, nunca por ORM directo. Hereda operator_a/operator_b,
    _request_as y _load_session_with_product de
    TestPreparationDayProductClaim (Fase B) para no duplicar fixture."""

    def setUp(self):
        super().setUp()
        self.Interval = self.env['guapante.preparation.interval']

    def _enter_l2(self, claim, employee):
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(employee)):
            claim.action_open_lines_kanban()

    def _weigh(self, line, employee, kg):
        mock_request = self._request_as(employee)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_request), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_request):
            line.with_context(guapante_picking_flow=True).write({
                'actual_kg': kg,
            })

    def _open_working(self, employee):
        return self.Interval.search([
            ('employee_id', '=', employee.id),
            ('kind', '=', 'working'),
            ('end_dt', '=', False),
        ])

    # ── Apertura ──

    def test_open_working_sets_start_and_last_touched_to_now(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 20, 5, 0)
            self._enter_l2(claim, self.operator_a)
        interval = self._open_working(self.operator_a)
        self.assertEqual(len(interval), 1)
        self.assertEqual(interval.claim_id, claim)
        self.assertEqual(interval.kind, 'working')
        self.assertEqual(interval.start_dt, datetime(2026, 11, 4, 20, 5, 0))
        self.assertEqual(interval.last_touched_dt, datetime(2026, 11, 4, 20, 5, 0))

    def test_open_working_reentry_same_claim_does_not_duplicate(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._enter_l2(claim, self.operator_a)
        first = self._open_working(self.operator_a)
        self._enter_l2(claim, self.operator_a)
        second = self._open_working(self.operator_a)
        self.assertEqual(first, second)
        self.assertEqual(
            self.Interval.search_count([
                ('employee_id', '=', self.operator_a.id),
            ]),
            1,
        )

    def test_open_working_switch_closes_previous_as_switched_with_last_touched(self):
        product_b = self.env['product.product'].create({
            'name': 'Producto Switch Test',
            'type': 'consu',
        })
        self._create_confirmed_order(qty=1.0, product=product_b)
        session = self._load_session_with_product()
        claim_a = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        claim_b = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == product_b.product_tmpl_id
        )
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 10, 0, 0)
            self._enter_l2(claim_a, self.operator_a)
            interval_a = self._open_working(self.operator_a)

            mock_now.return_value = datetime(2026, 11, 4, 10, 3, 0)
            self._enter_l2(claim_b, self.operator_a)

        interval_a.invalidate_recordset()
        self.assertEqual(interval_a.close_reason, 'switched')
        # Nunca now() del cambio de foco (10:03) — su propio
        # last_touched_dt, que nunca se tocó después de abrir (10:00).
        self.assertEqual(interval_a.end_dt, datetime(2026, 11, 4, 10, 0, 0))
        self.assertEqual(interval_a.duration_s, 0)

        interval_b = self._open_working(self.operator_a)
        self.assertEqual(interval_b.claim_id, claim_b)
        self.assertEqual(interval_b.start_dt, datetime(2026, 11, 4, 10, 3, 0))

    def test_two_employees_open_working_simultaneously_both_succeed(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._enter_l2(claim, self.operator_a)
        self._enter_l2(claim, self.operator_b)
        self.assertEqual(len(self._open_working(self.operator_a)), 1)
        self.assertEqual(len(self._open_working(self.operator_b)), 1)

    # ── El ejemplo exacto confirmado por Tech Lead (condición (b),
    #    2026-11-04): 20:05 entra, 20:06:30 y 20:08:10 pesa, se aleja sin
    #    cerrar nada — un cierre no explícito (acá, simulando el cron de
    #    las 10:00) usa last_touched_dt, NUNCA la hora del cierre. ──

    def test_example_20_05_20_06_30_20_08_10_closed_with_190_seconds(self):
        # Tres Cajas del mismo producto (tres pedidos de 1 unidad, no
        # qty=3.0 que daría una sola línea) — pesar solo dos deja el
        # claim sin terminar, así el intervalo sigue abierto para
        # simular el cierre del cron al final.
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        lines = session.line_ids
        self.assertEqual(len(lines), 3)

        t_enter = datetime(2026, 11, 4, 20, 5, 0)
        t_w1 = datetime(2026, 11, 4, 20, 6, 30)
        t_w2 = datetime(2026, 11, 4, 20, 8, 10)
        t_cron = datetime(2026, 11, 5, 10, 0, 0)

        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = t_enter
            self._enter_l2(claim, self.operator_a)
            interval = self._open_working(self.operator_a)
            self.assertEqual(interval.start_dt, t_enter)
            self.assertEqual(interval.last_touched_dt, t_enter)

            mock_now.return_value = t_w1
            self._weigh(lines[0], self.operator_a, 1.0)
            interval.invalidate_recordset()
            self.assertEqual(interval.last_touched_dt, t_w1)
            self.assertEqual(interval.first_weigh_dt, t_w1)
            self.assertEqual(interval.lines_done, 1)

            mock_now.return_value = t_w2
            self._weigh(lines[1], self.operator_a, 1.0)
            interval.invalidate_recordset()
            self.assertEqual(interval.last_touched_dt, t_w2)
            # first_weigh_dt se fija una sola vez — no se mueve.
            self.assertEqual(interval.first_weigh_dt, t_w1)
            self.assertEqual(interval.lines_done, 2)
            # Tercera Caja sin pesar — el claim no terminó, el
            # intervalo sigue abierto (ninguna rama lo cerró solo).
            self.assertFalse(interval.end_dt)

            # Simula el cierre del cron de abandono de las 10:00 del
            # día siguiente: cierra con el last_touched_dt del PROPIO
            # intervalo, nunca con "ahora" (las 10:00).
            mock_now.return_value = t_cron
            interval._close('idle', interval.last_touched_dt)

        self.assertEqual(interval.end_dt, t_w2)
        self.assertEqual(interval.duration_s, 190)

    def test_never_weighed_interval_closed_with_duration_zero(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        t_enter = datetime(2026, 11, 4, 9, 0, 0)
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = t_enter
            self._enter_l2(claim, self.operator_a)
            interval = self._open_working(self.operator_a)
            self.assertEqual(interval.start_dt, t_enter)
            self.assertEqual(interval.last_touched_dt, t_enter)

            mock_now.return_value = datetime(2026, 11, 5, 10, 0, 0)
            interval._close('idle', interval.last_touched_dt)

        self.assertEqual(interval.end_dt, t_enter)
        self.assertEqual(interval.duration_s, 0)

    # ── Pesaje: last_touched_dt, first_weigh_dt, lines_done/zero/kg ──

    def test_correction_on_done_line_does_not_increment_lines_done(self):
        # Dos Cajas (dos pedidos de 1 unidad, no qty=2.0 que da una sola
        # línea) — pesar y corregir solo la primera deja la segunda
        # pendiente, así el claim no termina y el intervalo sigue
        # abierto durante todo el test (si terminara, _close_finished_
        # intervals() lo cerraría y el helper _open_working ya no lo
        # encontraría — no es lo que este test quiere observar).
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        line = session.line_ids[0]
        self._enter_l2(claim, self.operator_a)
        self._weigh(line, self.operator_a, 1.0)
        interval = self._open_working(self.operator_a)
        self.assertEqual(interval.lines_done, 1)
        touched_after_first = interval.last_touched_dt

        # Corrección sobre la MISMA línea, ya Terminada — no es una
        # nueva línea (Fase 2: "corregir y volver a pesar una caja...
        # no cuenta como una nueva"), pero sigue siendo actividad real.
        self._weigh(line, self.operator_a, 1.5)
        interval.invalidate_recordset()
        self.assertEqual(interval.lines_done, 1)
        self.assertGreaterEqual(interval.last_touched_dt, touched_after_first)

    def test_zero_kg_weighing_counts_as_zero_lines_done(self):
        # Dos Cajas — ver comentario de test_correction_on_done_line_
        # does_not_increment_lines_done: despachar en 0 la primera no
        # debe terminar el claim (deja la segunda pendiente), para que
        # el intervalo siga abierto y el helper _open_working lo
        # encuentre.
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        line = session.line_ids[0]
        self._enter_l2(claim, self.operator_a)
        # E7 — despacho en 0 ("sin stock"): Terminada igual.
        self._weigh(line, self.operator_a, 0.0)
        self.assertTrue(line.is_done)
        interval = self._open_working(self.operator_a)
        self.assertEqual(interval.lines_done, 1)
        self.assertEqual(interval.zero_lines_done, 1)
        self.assertEqual(interval.kg_done, 0.0)

    def test_weighing_without_prior_l2_entry_opens_interval_as_backstop(self):
        """Respaldo documentado en _handle_weighing(): si por lo que sea
        se pesa sin haber pasado por action_open_lines_kanban primero,
        abre el intervalo ahí mismo — first_weigh_dt queda en start_dt
        (no hay cómo saber cuánto esperó antes de este pesaje).

        Dos Cajas (ver mismo comentario en los tests de arriba): pesar
        solo la primera no debe terminar el claim ni cerrar el
        intervalo recién abierto, para poder encontrarlo abierto al
        final del test."""
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        line = session.line_ids[0]
        self._weigh(line, self.operator_a, 1.0)
        interval = self._open_working(self.operator_a)
        self.assertEqual(len(interval), 1)
        self.assertEqual(interval.claim_id, claim)
        self.assertEqual(interval.first_weigh_dt, interval.start_dt)
        self.assertEqual(interval.lines_done, 1)

    # ── Cierres explícitos vs. no explícitos (condición (b)) ──

    def test_action_stop_closes_working_and_opens_informational_stopped(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        # action_stop exige un dueño actual — se asigna primero
        # (action_assign ya abre Nivel 2 al final, action_open_lines_
        # kanban() incluido, mismo intervalo que abriría _enter_l2).
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_assign()
        working = self._open_working(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_stop('sin_stock')
        working.invalidate_recordset()
        self.assertEqual(working.close_reason, 'stopped')
        self.assertTrue(working.end_dt)

        Stopped = self.Interval.search([
            ('claim_id', '=', claim.id),
            ('kind', '=', 'stopped'),
            ('end_dt', '=', False),
        ])
        self.assertEqual(len(Stopped), 1)
        self.assertEqual(Stopped.employee_id, self.operator_a)
        self.assertEqual(Stopped.stop_reason, 'sin_stock')

    def test_action_unstop_closes_both_stopped_and_any_open_working(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        # Bajo E3, cualquiera puede entrar a Nivel 2 de un Detenido
        # (ver action_open_lines_kanban) — operator_b entra a mirar
        # mientras sigue Detenido.
        self._enter_l2(claim, self.operator_b)
        working_b = self._open_working(self.operator_b)
        self.assertTrue(working_b)

        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_unstop()

        working_b.invalidate_recordset()
        self.assertEqual(working_b.close_reason, 'released')
        self.assertTrue(working_b.end_dt)
        self.assertFalse(self.Interval.search([
            ('claim_id', '=', claim.id),
            ('kind', '=', 'stopped'),
            ('end_dt', '=', False),
        ]))

    def test_action_release_closes_working_with_now_not_last_touched(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 8, 0, 0)
            # action_release exige un dueño actual.
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_assign()
            interval = self._open_working(self.operator_a)

            mock_now.return_value = datetime(2026, 11, 4, 9, 30, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_release()

        interval.invalidate_recordset()
        self.assertEqual(interval.close_reason, 'released')
        # Explícito (Liberar) — usa now() de la acción, no
        # last_touched_dt (que seguía en 8:00, nunca se tocó).
        self.assertEqual(interval.end_dt, datetime(2026, 11, 4, 9, 30, 0))
        self.assertEqual(interval.duration_s, 5400)

    def test_cron_abandonment_closes_working_with_last_touched_not_now(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 20, 0, 0)
            self._enter_l2(claim, self.operator_a)
            interval = self._open_working(self.operator_a)

            # Simula el cron de abandono de CLAIMS (plan f1) — no
            # explícito, pasa use_last_touched=True (condición (b)).
            mock_now.return_value = datetime(2026, 11, 5, 10, 0, 0)
            claim._release_claim(close_reason='idle', use_last_touched=True)

        interval.invalidate_recordset()
        self.assertEqual(interval.close_reason, 'idle')
        # Su propio last_touched_dt (20:00, nunca se tocó después de
        # abrir) — NUNCA la hora del cron (10:00 del día siguiente).
        self.assertEqual(interval.end_dt, datetime(2026, 11, 4, 20, 0, 0))
        self.assertEqual(interval.duration_s, 0)

    def test_clear_operator_closes_open_working_with_session_closed_reason(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._enter_l2(claim, self.operator_a)
        interval = self._open_working(self.operator_a)

        mock_a = self._request_as(self.operator_a)
        close_request = MagicMock()
        close_request.env = self.env
        close_request.session = dict(mock_a.session)
        with patch(IDENTIFICATION_REQUEST_PATCH_TARGET, close_request):
            PreparationDayIdentificationController().clear_operator()

        interval.invalidate_recordset()
        self.assertEqual(interval.close_reason, 'session_closed')
        self.assertTrue(interval.end_dt)

    def test_action_close_my_interval_closes_with_left_reason(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._enter_l2(claim, self.operator_a)
        interval = self._open_working(self.operator_a)

        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_close_my_interval()

        interval.invalidate_recordset()
        self.assertEqual(interval.close_reason, 'left')
        self.assertTrue(interval.end_dt)

    def test_action_close_my_interval_is_noop_when_nothing_open(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            result = claim.action_close_my_interval()
        self.assertTrue(result)

    def test_finishing_last_line_closes_working_of_every_viewer(self):
        """E3 (sin ownership): bajo _close_finished_intervals, terminar
        la última línea cierra el 'working' de CUALQUIERA que esté
        adentro, no solo del dueño — a propósito sin el filtro de
        assigned_employee_id que sí tiene _maybe_release_finished_claim."""
        session = self._load_session_with_product(qty=1.0)
        claim = session.product_claim_ids
        line = session.line_ids[0]
        self._enter_l2(claim, self.operator_a)
        self._enter_l2(claim, self.operator_b)
        working_a = self._open_working(self.operator_a)
        working_b = self._open_working(self.operator_b)
        self.assertTrue(working_a)
        self.assertTrue(working_b)

        self._weigh(line, self.operator_a, 1.0)

        working_a.invalidate_recordset()
        working_b.invalidate_recordset()
        self.assertEqual(working_a.close_reason, 'finished')
        self.assertEqual(working_b.close_reason, 'finished')
        self.assertTrue(working_a.end_dt)
        self.assertTrue(working_b.end_dt)
