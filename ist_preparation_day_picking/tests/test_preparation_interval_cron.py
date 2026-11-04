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
                          end_dt=None, close_reason=None):
        touched = fields.Datetime.now() - timedelta(days=days_ago)
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

    def test_cron_leaves_todays_open_interval_untouched(self):
        """Regla de la jornada (David, 2026-10-29): nunca toca nada de
        HOY, sin importar a qué hora corra el cron."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        interval = self._create_interval(
            claim, 'working', employee=self.operator_a, days_ago=0,
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
