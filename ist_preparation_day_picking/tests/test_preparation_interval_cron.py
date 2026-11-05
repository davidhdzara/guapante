# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from .test_preparation_day_product_claim import TestPreparationDayProductClaim


@tagged('post_install', '-at_install')
class TestPreparationIntervalCron(TestPreparationDayProductClaim):
    """Fase 2, commit 3/7 (Tech Lead, 2026-11-04) — cron diario de
    cierre de intervalos abandonados de una jornada anterior. Hereda
    operator_a/_load_session_with_product de TestPreparationDayProductClaim
    (Fase B) para no duplicar fixture.

    Los intervalos de estos tests se crean por ORM directo (no por
    _open_working, el camino normal) porque necesitan un start_dt fijo
    "de ayer" sin depender de mockear fields.Datetime.now() — es un
    test de caja blanca sobre el cron mismo, no sobre la apertura."""

    def setUp(self):
        super().setUp()
        self.Interval = self.env['guapante.preparation.interval']

    def _create_interval(self, claim, kind, employee=None, days_ago=0,
                          start_dt=None, end_dt=None, close_reason=None):
        touched = start_dt if start_dt is not None else (
            fields.Datetime.now() - timedelta(days=days_ago)
        )
        vals = {
            'wizard_id': claim.wizard_id.id,
            'claim_id': claim.id,
            'employee_id': employee.id if employee else False,
            'kind': kind,
            'start_dt': touched,
            'last_touched_dt': touched,
        }
        if end_dt is not None:
            vals['end_dt'] = end_dt
            vals['duration_s'] = 0
            vals['close_reason'] = close_reason
        return self.Interval.sudo().create(vals)

    def test_cron_closes_working_interval_from_prior_jornada_with_last_touched(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        interval = self._create_interval(
            claim, 'working', employee=self.operator_a, days_ago=2,
        )
        touched_at = interval.last_touched_dt

        self.Interval._cron_release_abandoned_intervals()

        interval.invalidate_recordset()
        self.assertEqual(interval.close_reason, 'idle')
        # Nunca "ahora" (cuando corrió el cron) — su propio
        # last_touched_dt, de hace 2 días (condición (b)).
        self.assertEqual(interval.end_dt, touched_at)
        self.assertEqual(interval.duration_s, 0)

    def test_cron_closes_stopped_interval_from_prior_jornada_too(self):
        """'Detenido' también es informativo-abandonable — un Detenido
        que nadie liberó de una jornada a otra también se cierra."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        interval = self._create_interval(claim, 'stopped', days_ago=3)

        self.Interval._cron_release_abandoned_intervals()

        interval.invalidate_recordset()
        self.assertEqual(interval.close_reason, 'idle')
        self.assertTrue(interval.end_dt)

    def test_cron_closes_unresumed_stopped_with_duration_from_start_not_zero(self):
        """Tech Lead, revisión de 3b/7 (commit 3c/7): last_touched_dt de
        un 'stopped' es siempre igual a su start_dt (nadie "toca" un
        Detenido), así que la regla de 'working' (end_dt=last_touched_dt)
        daría SIEMPRE duration_s=0 para 'stopped' — perdiendo el tiempo
        detenido real que David quiere medir. La sesión sigue sin
        cerrar (sin date_done), así que el cron debe usar su propio
        instante (now) como fin, no 0."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self.assertNotEqual(session.state, 'done')
        interval = self._create_interval(claim, 'stopped', days_ago=1)
        start_dt = interval.start_dt

        before_cron = fields.Datetime.now()
        self.Interval._cron_release_abandoned_intervals()
        after_cron = fields.Datetime.now()

        interval.invalidate_recordset()
        self.assertEqual(interval.close_reason, 'idle')
        # end_dt es el instante del cron (now), nunca last_touched_dt/
        # start_dt — por eso duration_s > 0, no 0.
        self.assertTrue(before_cron <= interval.end_dt <= after_cron)
        self.assertGreater(interval.duration_s, 0)
        self.assertEqual(
            interval.duration_s,
            int((interval.end_dt - start_dt).total_seconds()),
        )

    def test_cron_closes_stopped_with_session_done_using_date_done(self):
        """Cuando la sesión (guapante.preparation.day) ya cerró, su
        date_done es un límite real y conocido de "hasta cuándo estuvo
        detenido" — mejor que el instante del cron del día siguiente,
        que ya no tiene relación con cuándo terminó realmente la
        jornada."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        interval = self._create_interval(claim, 'stopped', days_ago=1)
        session.action_mark_done()
        self.assertEqual(session.state, 'done')
        self.assertTrue(session.date_done)
        date_done = session.date_done

        self.Interval._cron_release_abandoned_intervals()

        interval.invalidate_recordset()
        self.assertEqual(interval.close_reason, 'idle')
        self.assertEqual(interval.end_dt, date_done)
        self.assertEqual(
            interval.duration_s,
            int((date_done - interval.start_dt).total_seconds()),
        )

    def test_cron_closes_early_morning_interval_from_same_calendar_day(self):
        """Regla corregida (David/Tech Lead, 2026-11-04, commit 3b/7 —
        "abandonada SIEMPRE a las 10:00"): un intervalo abierto de
        madrugada DEL MISMO día calendario en que corre el cron (ej.
        tablet muerta a la 01:00) también se cierra — la versión
        anterior lo dejaba abierto ~24h más, hasta el cron del día
        siguiente, por comparar contra la medianoche de hoy en vez de
        contra "ahora"."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        early_morning = fields.Datetime.now() - timedelta(hours=3)
        interval = self._create_interval(
            claim, 'working', employee=self.operator_a,
            start_dt=early_morning,
        )

        self.Interval._cron_release_abandoned_intervals()

        interval.invalidate_recordset()
        self.assertEqual(interval.close_reason, 'idle')
        self.assertEqual(interval.end_dt, early_morning)

    def test_cron_leaves_interval_started_after_cron_moment_untouched(self):
        """Borde de la condición start_dt < ahora: un intervalo cuyo
        start_dt es POSTERIOR al instante en que corre el cron (ej. se
        abrió literalmente mientras corría la corrida anterior, o un
        reloj desincronizado) no se toca — todavía no puede ser
        "abandonado" si ni siquiera empezó antes de este chequeo."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        future = fields.Datetime.now() + timedelta(minutes=5)
        interval = self._create_interval(
            claim, 'working', employee=self.operator_a, start_dt=future,
        )

        self.Interval._cron_release_abandoned_intervals()

        interval.invalidate_recordset()
        self.assertFalse(interval.end_dt)
        self.assertFalse(interval.close_reason)

    def test_cron_is_noop_on_already_closed_interval(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        old_end = fields.Datetime.now() - timedelta(days=2, minutes=-5)
        interval = self._create_interval(
            claim, 'working', employee=self.operator_a, days_ago=2,
            end_dt=old_end, close_reason='left',
        )

        self.Interval._cron_release_abandoned_intervals()

        interval.invalidate_recordset()
        # No lo vuelve a tocar — ya estaba cerrado por otra vía.
        self.assertEqual(interval.close_reason, 'left')
        self.assertEqual(interval.end_dt, old_end)

    def test_cron_does_not_raise_when_nothing_to_close(self):
        self.Interval._cron_release_abandoned_intervals()
