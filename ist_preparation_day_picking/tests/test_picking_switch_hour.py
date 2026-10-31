# -*- coding: utf-8 -*-
"""Corrección #12, Tech Lead/David 2026-10-31: la operación real de
Guapante empieza a las 22:00 del día anterior — el TABLET de Picking
debe resolver "mañana" desde una hora configurable (no al llegar la
medianoche). Cubre _picking_session_date (ist_preparation_day_picking/
models/preparation_day.py), usada ÚNICAMENTE por
action_resolve_picking_handoff — nunca por el cron de respaldo ni por
el corte 00:30 de action_confirm (ambos siguen en _current_session_date,
sin tocar).
"""
from datetime import datetime, time, timedelta
from unittest.mock import patch

import pytz

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)
from odoo.addons.ist_preparation_day_picking.models.preparation_day import (
    _PICKING_SWITCH_HOUR_PARAM_KEY,
    _picking_session_date,
)

BOGOTA_TZ = pytz.timezone('America/Bogota')


@tagged('post_install', '-at_install')
class TestPickingSwitchHour(TestPreparationDay):

    def _now_at(self, day, hour, minute):
        return BOGOTA_TZ.localize(
            datetime.combine(day, time(hour, minute)),
        ).astimezone(pytz.utc).replace(tzinfo=None)

    def _session_date_at(self, day, hour, minute):
        with patch(
            'odoo.fields.Datetime.now',
            return_value=self._now_at(day, hour, minute),
        ):
            return _picking_session_date(self.env)

    def test_before_switch_hour_resolves_today(self):
        self.assertEqual(
            self._session_date_at(self.delivery_date, 20, 59),
            self.delivery_date,
        )

    def test_at_switch_hour_resolves_tomorrow(self):
        self.assertEqual(
            self._session_date_at(self.delivery_date, 21, 0),
            self.delivery_date + timedelta(days=1),
        )

    def test_late_night_resolves_tomorrow(self):
        self.assertEqual(
            self._session_date_at(self.delivery_date, 23, 59),
            self.delivery_date + timedelta(days=1),
        )

    def test_early_morning_resolves_today_since_today_is_already_d(self):
        """00:05 — el día calendario YA es D, no hay que sumarle nada:
        hora 0 < hora de corte (21:00), se resuelve 'hoy' = D."""
        self.assertEqual(
            self._session_date_at(self.delivery_date, 0, 5),
            self.delivery_date,
        )

    def test_invalid_param_falls_back_to_default_21_00(self):
        self.env['ir.config_parameter'].sudo().set_param(
            _PICKING_SWITCH_HOUR_PARAM_KEY, 'no-es-una-hora',
        )
        self.assertEqual(
            self._session_date_at(self.delivery_date, 21, 30),
            self.delivery_date + timedelta(days=1),
            'parámetro inválido debe caer al default 21:00, no reventar '
            'ni quedarse pegado a "hoy"',
        )

    def test_past_switch_hour_with_today_done_resolves_tomorrow(self):
        Session = self.env[
            'guapante.preparation.day'
        ]._ensure_session_for_date(self.delivery_date)
        Session.action_mark_done()

        self.assertEqual(
            self._session_date_at(self.delivery_date, 21, 30),
            self.delivery_date + timedelta(days=1),
        )

    def test_past_switch_hour_with_today_pending_lines_stays_today(self):
        """Condición de seguridad operativa (Tech Lead 2026-10-31): un
        turno que se alarga NO debe saltar a una sesión de mañana
        todavía vacía mientras hoy tenga trabajo pendiente."""
        Session = self.env[
            'guapante.preparation.day'
        ]._ensure_session_for_date(self.delivery_date)
        self.env['guapante.preparation.day.line'].create({
            'wizard_id': Session.id,
            'product_product_id': self.product_weight.id,
            'estimated_kg': 5.0,
            'order_name': 'S-TEST-SWITCH-HOUR',
        })
        Session.sudo().write({'state': 'loaded'})

        self.assertEqual(
            self._session_date_at(self.delivery_date, 21, 30),
            self.delivery_date,
        )

    def test_past_switch_hour_with_no_session_today_resolves_tomorrow(self):
        self.assertFalse(
            self.env['guapante.preparation.day'].search(
                [('date', '=', self.delivery_date)], limit=1,
            ),
        )
        self.assertEqual(
            self._session_date_at(self.delivery_date, 21, 30),
            self.delivery_date + timedelta(days=1),
        )
