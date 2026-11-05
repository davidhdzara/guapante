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
        """'Entrar a Nivel 2' en el flujo real (Fase 2, lote B,
        rediseño de continuidad): hoy ES Asignarme — action_open_
        lines_kanban() por sí sola ya NO abre el intervalo, salvo la
        excepción acotada del propio dueño sin intervalo (ver su
        docstring, probada aparte más abajo). Los fixtures de este
        archivo siempre parten de un claim 'pending', así que
        action_assign() es el equivalente correcto a "entrar"."""
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(employee)):
            claim.action_assign()

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
        """Reentrada real sobre un claim ya propio (Tech Lead,
        excepción acotada de B.2a): "Continuar" (action_open_lines_
        kanban directo, sin volver a pasar por Asignarme — eso
        reventaría con "ya se asignó", ver action_assign) sobre un
        claim que YA es mío y ya tiene 'working' abierto no debe
        duplicar ni reabrir nada."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._enter_l2(claim, self.operator_a)
        first = self._open_working(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_open_lines_kanban()
        second = self._open_working(self.operator_a)
        self.assertEqual(first, second)
        self.assertEqual(
            self.Interval.search_count([
                ('employee_id', '=', self.operator_a.id),
            ]),
            1,
        )

    def test_open_working_switch_closes_previous_as_switched_with_last_touched(self):
        """Switch real bajo el nuevo diseño (Tech Lead, B.2a): ya no
        se da por "Continuar" sobre otro producto (eso ya no abre
        nada) — se da cuando el operario tenía un 'working' de
        RESPALDO abierto en un producto SIN dueño (pesaje ad-hoc bajo
        E3) y luego Asignarme lo toma a él mismo para OTRO producto:
        _open_working() cierra el primero como 'switched' con su
        propio last_touched_dt antes de abrir el nuevo."""
        product_b = self.env['product.product'].create({
            'name': 'Producto Switch Test',
            'type': 'consu',
        })
        self._create_confirmed_order(qty=1.0, product=product_b)
        self._create_confirmed_order(qty=1.0, product=product_b)
        session = self._load_session_with_product()
        claim_a = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        claim_b = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == product_b.product_tmpl_id
        )
        lines_b = claim_b._get_lines()
        self.assertEqual(len(lines_b), 2)
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 10, 0, 0)
            # Pesaje ad-hoc sobre B sin Asignarme (claim_b sigue
            # 'pending') — respaldo de _handle_weighing abre el
            # 'working' acá. Una sola de las 2 líneas: el claim no
            # termina, el intervalo sigue abierto para el switch.
            self._weigh(lines_b[0], self.operator_a, 1.0)
            interval_b = self._open_working(self.operator_a)
            self.assertEqual(interval_b.claim_id, claim_b)
            self.assertFalse(interval_b.end_dt)

            mock_now.return_value = datetime(2026, 11, 4, 10, 3, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim_a.action_assign()

        interval_b.invalidate_recordset()
        self.assertEqual(interval_b.close_reason, 'switched')
        # Nunca now() del cambio de foco (10:03) — su propio
        # last_touched_dt, que nunca se tocó después de abrir (10:00).
        self.assertEqual(interval_b.end_dt, datetime(2026, 11, 4, 10, 0, 0))
        self.assertEqual(interval_b.duration_s, 0)

        interval_a = self._open_working(self.operator_a)
        self.assertEqual(interval_a.claim_id, claim_a)
        self.assertEqual(interval_a.start_dt, datetime(2026, 11, 4, 10, 3, 0))

    def test_two_employees_open_working_on_different_claims_both_succeed(self):
        """Bajo el nuevo diseño (Fase 2, lote B), dos operarios ya NO
        pueden tener 'working' abierto sobre el MISMO claim a la vez
        (la apertura normal queda condicionada a ser el dueño) — pero
        sí, cada uno, sobre SU PROPIO claim distinto, sin
        interferirse."""
        product_b = self.env['product.product'].create({
            'name': 'Producto Dos Operarios', 'type': 'consu',
        })
        self._create_confirmed_order(qty=1.0, product=product_b)
        session = self._load_session_with_product()
        claim_a = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        claim_b = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == product_b.product_tmpl_id
        )
        self._enter_l2(claim_a, self.operator_a)
        self._enter_l2(claim_b, self.operator_b)
        self.assertEqual(len(self._open_working(self.operator_a)), 1)
        self.assertEqual(len(self._open_working(self.operator_b)), 1)

    # ── get_my_open_interval (lectura de solo consulta, lote 2B —
    #    fuente de start_dt/server_now para el cronómetro de Nivel 2) ──

    def test_get_my_open_interval_returns_start_dt_and_server_now(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 10, 0, 0)
            self._enter_l2(claim, self.operator_a)

        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 10, 3, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                result = claim.get_my_open_interval()

        self.assertEqual(result['start_dt'], datetime(2026, 11, 4, 10, 0, 0))
        self.assertEqual(result['server_now'], datetime(2026, 11, 4, 10, 3, 0))

    def test_get_my_open_interval_returns_false_start_dt_when_nothing_open(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            result = claim.get_my_open_interval()
        self.assertFalse(result['start_dt'])
        self.assertTrue(result['server_now'])

    def test_get_my_open_interval_scoped_to_own_employee_only(self):
        """Cada cronómetro ve solo el propio intervalo, nunca el de
        otro operario — demostrado con cada uno en su propio claim
        (bajo el nuevo diseño, dos operarios ya no comparten 'working'
        abierto en el MISMO claim — ver test_two_employees_open_
        working_on_different_claims_both_succeed)."""
        product_b = self.env['product.product'].create({
            'name': 'Producto Scoped Test', 'type': 'consu',
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
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 10, 1, 0)
            self._enter_l2(claim_b, self.operator_b)

        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            result_a = claim_a.get_my_open_interval()
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_b)):
            result_b = claim_b.get_my_open_interval()

        self.assertEqual(result_a['start_dt'], datetime(2026, 11, 4, 10, 0, 0))
        self.assertEqual(result_b['start_dt'], datetime(2026, 11, 4, 10, 1, 0))

    def test_get_my_open_interval_without_active_operator_returns_false(self):
        """Sin operario identificado (NIP vencido entre medio) — nunca
        revienta, solo informa que no hay nada que mostrar; el cliente
        ya maneja ese mensaje en otros caminos (_handleError)."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        mock_request = MagicMock()
        mock_request.session = {}
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_request):
            result = claim.get_my_open_interval()
        self.assertFalse(result['start_dt'])

    # ── Tarea 5 (Tech Lead/David, 2026-11-05): accumulated_s de
    #    get_my_open_interval() — suma de MIS intervalos 'working' ya
    #    CERRADOS sobre este claim; el abierto nunca se cuenta acá
    #    (ese elapsed lo suma el cliente con start_dt/server_now, ver
    #    preparation_picking_visit_timer.js). ──

    def test_get_my_open_interval_accumulated_s_sums_only_closed_intervals(self):
        """Con un único 'working' abierto (recién entrado, sin cierres
        previos) accumulated_s debe ser 0 — el elapsed del abierto lo
        calcula el cliente, nunca este campo."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 5, 9, 0, 0)
            self._enter_l2(claim, self.operator_a)

        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 5, 9, 5, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                result = claim.get_my_open_interval()

        self.assertEqual(result['accumulated_s'], 0)
        self.assertEqual(result['start_dt'], datetime(2026, 11, 5, 9, 0, 0))

    def test_get_my_open_interval_accumulated_s_persists_across_stop_resume(self):
        """El requisito central de la Tarea 5: el acumulado del mismo
        operario sobre el mismo claim NUNCA vuelve a 00:00 por un
        ciclo Detener → Retomar — accumulated_s suma el 'working' que
        Detener cierra, y un segundo ciclo sigue sumando sobre ese
        total, nunca lo reinicia."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids

        t0 = datetime(2026, 11, 5, 9, 0, 0)
        t1 = datetime(2026, 11, 5, 9, 2, 0)  # 1er 'working': 120s
        t2 = datetime(2026, 11, 5, 9, 10, 0)  # Retomar
        t3 = datetime(2026, 11, 5, 9, 10, 50)  # 2do 'working': 50s

        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = t0
            self._enter_l2(claim, self.operator_a)

        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = t1
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_stop('otro')

        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            result_after_first_stop = claim.get_my_open_interval()
        self.assertEqual(result_after_first_stop['accumulated_s'], 120)
        self.assertFalse(result_after_first_stop['start_dt'])

        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = t2
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_resume()

        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = t3
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_stop('otro')

        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            result_after_second_stop = claim.get_my_open_interval()
        self.assertEqual(result_after_second_stop['accumulated_s'], 170)
        self.assertFalse(result_after_second_stop['start_dt'])

    def test_get_my_open_interval_second_operator_starts_at_zero(self):
        """Un segundo operario que entra al MISMO claim por primera
        vez (vía Retomar, tras un Detener del primero) no tiene
        intervalos cerrados propios todavía — su accumulated_s es 0,
        sin importar cuánto acumuló el primero sobre el mismo claim."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids

        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 5, 9, 0, 0)
            self._enter_l2(claim, self.operator_a)
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 5, 9, 3, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_stop('otro')

        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 5, 9, 5, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_b)):
                claim.action_resume()

        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_b)):
            result_b = claim.get_my_open_interval()
        self.assertEqual(result_b['accumulated_s'], 0)
        self.assertEqual(result_b['start_dt'], datetime(2026, 11, 5, 9, 5, 0))

        # El acumulado del operario A, dueño anterior, queda intacto.
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            result_a = claim.get_my_open_interval()
        self.assertEqual(result_a['accumulated_s'], 180)

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

    def test_open_working_failure_does_not_block_the_weighing(self):
        """Tech Lead, revisión de 4/7 (principio rector reforzado,
        2026-11-04): el tiempo es dato SECUNDARIO. Si _open_working
        (acá disparado como respaldo desde _handle_weighing, por
        pesar sin pasar antes por Nivel 2 — ver el test de arriba)
        lanza una excepción inesperada, el pesaje real (is_done/
        actual_kg, escrito por super().write() ANTES de llegar a los
        intervalos en PreparationDayLine.write()) debe quedar
        guardado igual — _run_isolated aísla el fallo en su propio
        SAVEPOINT y sigue, sin tumbar lo que ya se guardó."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        line = session.line_ids[0]

        IntervalModel = self.env.registry['guapante.preparation.interval']
        with patch.object(
            IntervalModel, '_open_working',
            side_effect=Exception('boom: fallo simulado de intervalos'),
        ):
            self._weigh(line, self.operator_a, 2.5)

        line.invalidate_recordset()
        self.assertTrue(line.is_done)
        self.assertEqual(line.actual_kg, 2.5)
        # Se pierde el dato de TIEMPO de este pesaje (nunca se pudo
        # abrir el intervalo) — eso es lo esperado, nunca el pesaje.
        self.assertFalse(self._open_working(self.operator_a))

    def test_two_consecutive_weighings_same_operator_increments_lines_done_twice(self):
        """Nota de Tech Lead (revisión del commit 2/7): el read-modify-
        write de lines_done/kg_done en _register_weighing no tiene
        lock de fila explícito — es seguro porque un operario tiene un
        solo 'working' abierto a la vez y el flujo real del tablet es
        síncrono (ver el comentario ampliado en _register_weighing).
        Dos pesajes SEGUIDOS del mismo operario sobre el mismo
        intervalo deben sumar, no pisarse: tres Cajas, se pesan dos y
        la tercera queda pendiente (para que el claim no termine y
        _close_finished_intervals no cierre el intervalo antes de
        poder observarlo) — lines_done termina en 2."""
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        lines = session.line_ids
        self._enter_l2(claim, self.operator_a)
        self._weigh(lines[0], self.operator_a, 1.0)
        self._weigh(lines[1], self.operator_a, 1.0)
        interval = self._open_working(self.operator_a)
        self.assertEqual(len(interval), 1)
        self.assertEqual(interval.lines_done, 2)
        self.assertEqual(interval.kg_done, 2.0)

    def test_admin_edit_from_productos_tab_does_not_touch_intervals(self):
        """Nota de Tech Lead (revisión del commit 2/7): la edición de
        admin desde la pestaña Productos de Preparación (sin
        guapante_picking_flow en contexto — no viene del tablet) NO
        debe abrir ni tocar ningún intervalo — ese pesaje no tiene
        operario físico identificado por PIN, no hay reloj de nadie
        que registrar."""
        session = self._load_session_with_product()
        line = session.line_ids[0]
        # Sin with_context(guapante_picking_flow=True) — la misma
        # escritura que haría un admin desde Preparación.
        line.write({'actual_kg': 1.0})
        self.assertTrue(line.is_done)
        # Acotado a la sesión propia del test (Tech Lead, endurecimiento
        # 2026-11-04): sin dominio, este assert choca con cualquier
        # intervalo real que ya exista en la base (ej. una prueba en
        # vivo de David en staging_dev) — el punto del test es que ESTA
        # sesión no abrió nada, no que la tabla entera esté vacía.
        self.assertFalse(
            self.Interval.search([('wizard_id', '=', session.id)])
        )

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
        # Dos Cajas (no qty=2.0 en una sola — ver el mismo comentario
        # en los tests de pesaje más abajo): pesar solo UNA deja el
        # claim sin terminar, para que siga 'stopped' (si terminara,
        # action_unstop() rechazaría con "ya está terminado").
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        lines = session.line_ids
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        # Bajo E3, cualquiera puede pesar/corregir una línea de un
        # Detenido sin pasar por Retomar (_check_picking_ownership ya
        # no exige dueño) — action_stop() cerró el 'working' de todos
        # al detener, así que esta corrección ad-hoc de operator_b
        # dispara el respaldo de _handle_weighing (nadie tiene
        # 'working' abierto en este claim todavía).
        self._weigh(lines[0], self.operator_b, 1.0)
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

    def test_action_unstop_closes_stopped_interval_with_now_not_start_dt(self):
        """Nota de Tech Lead (revisión del commit 3b/7): confirmar con
        test que action_unstop() cierra el 'stopped' con now() — nunca
        con su propio start_dt/last_touched_dt (que para un 'stopped'
        son siempre iguales, ver docstring de la clase: nadie "toca"
        un Detenido). Explícito (acción del operario), así que SÍ usa
        la hora real de la acción, a diferencia del cron de abandono
        (commit 3c/7), que no tiene una acción explícita que marque el
        fin."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 8, 0, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_assign()
                claim.action_stop('sin_stock')
            Stopped = self.Interval.search([
                ('claim_id', '=', claim.id), ('kind', '=', 'stopped'),
            ])
            self.assertEqual(Stopped.start_dt, datetime(2026, 11, 4, 8, 0, 0))

            mock_now.return_value = datetime(2026, 11, 4, 14, 30, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_unstop()

        Stopped.invalidate_recordset()
        self.assertEqual(Stopped.end_dt, datetime(2026, 11, 4, 14, 30, 0))
        self.assertEqual(Stopped.duration_s, 6 * 3600 + 30 * 60)

    def test_action_resume_closes_the_open_stopped_interval(self):
        """Fase 2, lote B (bug encontrado por Odoo Engineer, 2026-11-04):
        a diferencia de action_unstop(), action_resume() no cerraba el
        'stopped' que action_stop() dejó abierto — quedaba huérfano para
        siempre (el cron de abandono de claims solo mira status=
        'in_progress', nunca lo iba a tocar). close_reason='resumed'
        (nuevo, distinto de 'released': acá alguien SE TOMA el
        producto, no lo libera sin dueño)."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 8, 0, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_assign()
                claim.action_stop('sin_stock')

            mock_now.return_value = datetime(2026, 11, 4, 8, 20, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_b)):
                claim.action_resume()

        Stopped = self.Interval.search([
            ('claim_id', '=', claim.id), ('kind', '=', 'stopped'),
        ])
        self.assertEqual(len(Stopped), 1)
        self.assertEqual(Stopped.close_reason, 'resumed')
        self.assertEqual(Stopped.end_dt, datetime(2026, 11, 4, 8, 20, 0))
        self.assertEqual(Stopped.duration_s, 20 * 60)

    def test_action_resume_failure_does_not_block_resuming(self):
        """Mismo principio rector que el resto del archivo (4/7): un
        fallo inesperado al cerrar el 'stopped' nunca debe impedir que
        Retomar haga su trabajo real (stop_reason limpio, claim
        asignado)."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')

        IntervalModel = self.env.registry['guapante.preparation.interval']
        with patch.object(
            IntervalModel, '_close_open_for_claim',
            side_effect=Exception('boom: fallo simulado de intervalos'),
        ):
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_b)):
                claim.action_resume()

        claim.invalidate_recordset()
        self.assertEqual(claim.assigned_employee_id, self.operator_b)
        self.assertFalse(claim.stop_reason)

    def test_stopped_interval_duration_independent_of_stopper_working_interval(self):
        """Verifica que el tiempo Detenido no se mezcla con el
        'working' de quien detiene: son DOS filas separadas, cada una
        con su propia duración, sin que una le reste ni le sume nada a
        la otra."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 8, 0, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_assign()

            mock_now.return_value = datetime(2026, 11, 4, 8, 10, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_stop('sin_stock')

            mock_now.return_value = datetime(2026, 11, 4, 9, 0, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_unstop()

        Working = self.Interval.search([
            ('claim_id', '=', claim.id), ('kind', '=', 'working'),
        ])
        Stopped = self.Interval.search([
            ('claim_id', '=', claim.id), ('kind', '=', 'stopped'),
        ])
        self.assertEqual(len(Working), 1)
        self.assertEqual(len(Stopped), 1)
        # El 'working' duró 10 minutos (8:00 a 8:10, cerrado por
        # action_stop con last_touched_dt == start_dt al no haber
        # pesado nada) — el 'stopped' duró 50 minutos (8:10 a 9:00,
        # cerrado por action_unstop con now()) — ninguna se contamina
        # con la otra.
        self.assertEqual(Working.duration_s, 10 * 60)
        self.assertEqual(Stopped.duration_s, 50 * 60)

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

    def test_leave_and_reenter_same_claim_keeps_same_interval(self):
        """B cliente (Tech Lead, 2026-11-04): se quitó el cierre al
        salir de Nivel 2 ("← Productos" ya no llama a ningún RPC de
        cierre — el método de servidor correspondiente,
        action_close_my_interval, también se eliminó). "Salir" es
        ahora navegación pura del cliente: no cierra nada en el
        servidor. Un reingreso al mismo claim (action_open_lines_
        kanban directo — el claim sigue siendo mío, no vuelvo a pasar
        por Asignarme) debe encontrar el MISMO intervalo todavía
        abierto, no uno nuevo — mismo id, mismo start_dt, el
        cronómetro de Nivel 1 sigue corriendo desde que entré la
        primera vez."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 10, 0, 0)
            self._enter_l2(claim, self.operator_a)
        first = self._open_working(self.operator_a)
        self.assertEqual(len(first), 1)
        self.assertEqual(first.start_dt, datetime(2026, 11, 4, 10, 0, 0))

        # "← Productos" (navegación pura, sin RPC) y luego "Continuar"
        # (action_open_lines_kanban directo) un rato después.
        with patch('odoo.fields.Datetime.now') as mock_now:
            mock_now.return_value = datetime(2026, 11, 4, 10, 10, 0)
            with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
                claim.action_open_lines_kanban()
        second = self._open_working(self.operator_a)
        self.assertEqual(second, first)
        self.assertEqual(second.start_dt, datetime(2026, 11, 4, 10, 0, 0))
        self.assertFalse(second.end_dt)
        self.assertEqual(
            self.Interval.search_count([
                ('employee_id', '=', self.operator_a.id),
            ]),
            1,
        )

    def test_finishing_last_line_closes_the_working_interval(self):
        """_close_finished_intervals cierra TODO 'working' abierto del
        claim al terminar la última línea — defensivo ante más de uno
        abierto a la vez, aunque bajo el nuevo diseño (Fase 2, lote B)
        eso ya no se da en el flujo normal (un claim 'in_progress'
        tiene un solo dueño, y el respaldo de pesaje nunca abre un
        segundo 'working' si ya hay uno de otro operario — ver el
        ajuste de atribución cruzada más abajo). Caso simple: el
        'working' del dueño se cierra como 'finished' al terminar."""
        session = self._load_session_with_product(qty=1.0)
        claim = session.product_claim_ids
        line = session.line_ids[0]
        self._enter_l2(claim, self.operator_a)
        working_a = self._open_working(self.operator_a)
        self.assertTrue(working_a)

        self._weigh(line, self.operator_a, 1.0)

        working_a.invalidate_recordset()
        self.assertEqual(working_a.close_reason, 'finished')
        self.assertTrue(working_a.end_dt)

    def test_cross_operator_weighing_on_owners_claim_gets_no_credit(self):
        """Ajuste de atribución cruzada (Tech Lead, B.2, respaldo/
        atribución en _handle_weighing): si B pesa/corrige sobre un
        claim cuyo 'working' abierto es de A (el dueño), esa pesaje NO
        abre un intervalo propio para B ni le toca nada al de A — el
        reparto por operario sigue viniendo de done_by_employee_id en
        la línea (Reporte 1), nunca de este intervalo. El pesaje REAL
        (is_done/actual_kg) se guarda igual — el tiempo es dato
        secundario, nunca bloquea el camino crítico.

        Tarea 7 (Tech Lead/David, 2026-11-05) — verificación de la
        regla de atribución ya implementada, sin cambio de código: un
        administrador/ayudante que pesa un producto que NO es suyo no
        suma tiempo a NADIE (ya cubierto arriba: ni B abre intervalo
        propio, ni se le toca el de A), pero el crédito de LÍNEA
        siempre queda con quien efectivamente la cerró — acá B, nunca
        A ni el dueño nominal del claim. Ambas mitades de la regla se
        prueban en la MISMA escritura, no por separado."""
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        claim = session.product_claim_ids
        lines = session.line_ids
        self._enter_l2(claim, self.operator_a)
        interval_a = self._open_working(self.operator_a)
        touched_before = interval_a.last_touched_dt
        lines_done_before = interval_a.lines_done

        self._weigh(lines[0], self.operator_b, 1.0)

        # Mitad 1 — tiempo: nadie se lleva crédito por este pesaje.
        self.assertFalse(self._open_working(self.operator_b))
        interval_a.invalidate_recordset()
        self.assertEqual(interval_a.last_touched_dt, touched_before)
        self.assertEqual(interval_a.lines_done, lines_done_before)
        # Mitad 2 — línea: el crédito es de quien efectivamente pesó
        # (B), nunca del dueño nominal del claim (A).
        self.assertTrue(lines[0].is_done)
        self.assertEqual(lines[0].done_by_employee_id, self.operator_b)

    def test_other_operator_backup_open_on_different_claim_does_not_touch_my_working(self):
        """"Entrar a otro producto bajo E3 no corta mi propio
        cronómetro" (cobertura obligatoria de B.2, Tech Lead): el
        respaldo de B sobre un producto DISTINTO, sin dueño, no toca
        para nada el 'working' que A tiene abierto en el suyo."""
        product_c = self.env['product.product'].create({
            'name': 'Producto C sin dueño', 'type': 'consu',
        })
        # Dos Cajas (no una sola — ver el mismo comentario en el test
        # de switch): pesar solo UNA deja claim_c sin terminar, para
        # que el 'working' de respaldo de B siga abierto cuando el
        # test lo observa (si claim_c terminara, _close_finished_
        # intervals lo cerraría como 'finished' en el mismo write()).
        self._create_confirmed_order(qty=1.0, product=product_c)
        self._create_confirmed_order(qty=1.0, product=product_c)
        session = self._load_session_with_product()
        claim_a = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        claim_c = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == product_c.product_tmpl_id
        )
        line_c = claim_c._get_lines()[0]
        self._enter_l2(claim_a, self.operator_a)
        interval_a = self._open_working(self.operator_a)
        start_before = interval_a.start_dt

        self._weigh(line_c, self.operator_b, 1.0)

        interval_a.invalidate_recordset()
        self.assertFalse(interval_a.end_dt)
        self.assertEqual(interval_a.start_dt, start_before)
        interval_c = self._open_working(self.operator_b)
        self.assertEqual(interval_c.claim_id, claim_c)
