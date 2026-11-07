# -*- coding: utf-8 -*-
"""Pantalla A (PDS Operación) — Tech Lead, plan aprobado 2026-11-06, 3
ajustes. Cubre get_pds_operacion_board_data(): agrupación en las 4
columnas, stop_reason visible solo en Detenido, operario visible solo
en En progreso/Terminado (igual que el mockup — confirmado en el
análisis previo), conteos coherentes con total_lines/done_lines/
pending_lines, control de acceso (group_preparation_admin sí,
operario de Picking AccessError — ajuste 3), y "Sin jornada abierta"
cuando _picking_session_date (ajuste 2 — NO _current_session_date) no
resuelve ninguna sesión real."""
import uuid
from datetime import datetime, time
from unittest.mock import patch

import pytz

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .test_preparation_day_product_claim import (
    REQUEST_PATCH_TARGET,
    TestPreparationDayProductClaim,
)

BOGOTA_TZ = pytz.timezone('America/Bogota')


@tagged('post_install', '-at_install')
class TestPreparationPdsOperacion(TestPreparationDayProductClaim):

    def setUp(self):
        super().setUp()
        self.admin_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin',
        )
        self.operator_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_picking_operator',
        )
        self.internal_group = self.env.ref('base.group_user')
        self.prep_admin_user = self.env['res.users'].create({
            'name': 'Admin Preparación Test (PDS)',
            'login': f'prep.admin.pds.test.{uuid.uuid4().hex}@example.com',
            'groups_id': [(6, 0, [
                self.admin_group.id, self.internal_group.id,
            ])],
        })
        self.prep_operator_user = self.env['res.users'].create({
            'name': 'Operario Test (PDS)',
            'login': f'prep.operator.pds.test.{uuid.uuid4().hex}@example.com',
            'groups_id': [(6, 0, [
                self.operator_group.id, self.internal_group.id,
            ])],
        })

    def _now_before_switch_hour(self):
        """UTC equivalente a las 10:00 locales de self.delivery_date —
        siempre antes del corte (21:00 por defecto) para que
        _picking_session_date, usada POR el propio método bajo
        prueba, resuelva exactamente self.delivery_date. Mismo
        mecanismo que test_picking_switch_hour.py."""
        return BOGOTA_TZ.localize(
            datetime.combine(self.delivery_date, time(10, 0)),
        ).astimezone(pytz.utc).replace(tzinfo=None)

    def _get_board_data_as_admin(self):
        with patch(
            'odoo.fields.Datetime.now', return_value=self._now_before_switch_hour(),
        ):
            return self.env[
                'guapante.preparation.day'
            ].with_user(self.prep_admin_user).get_pds_operacion_board_data()

    # ── Acceso (ajuste 3) ──

    def test_admin_can_call(self):
        session = self._load_session_with_product()
        data = self._get_board_data_as_admin()
        self.assertTrue(data['has_session'])
        self.assertEqual(data['session_id'], session.id)

    def test_operator_gets_access_error(self):
        self._load_session_with_product()
        with patch(
            'odoo.fields.Datetime.now', return_value=self._now_before_switch_hour(),
        ):
            with self.assertRaises(AccessError):
                self.env[
                    'guapante.preparation.day'
                ].with_user(
                    self.prep_operator_user
                ).get_pds_operacion_board_data()

    # ── Sesión resuelta vía _picking_session_date, no _current_session_date (ajuste 2) ──

    def test_no_session_for_target_date_signals_sin_jornada(self):
        data = self._get_board_data_as_admin()
        self.assertFalse(data['has_session'])
        self.assertEqual(data['session_date'], str(self.delivery_date))

    # ── Agrupación por columna / campos por tarjeta ──

    def test_pending_claim_has_no_operator_or_stop_reason(self):
        self._load_session_with_product()
        data = self._get_board_data_as_admin()
        pending = data['columns']['pending']
        self.assertEqual(len(pending), 1)
        self.assertNotIn('operator_name', pending[0])
        self.assertNotIn('stop_reason_label', pending[0])

    def test_in_progress_claim_shows_operator_name_not_stop_reason(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        data = self._get_board_data_as_admin()
        in_progress = data['columns']['in_progress']
        self.assertEqual(len(in_progress), 1)
        self.assertEqual(in_progress[0]['operator_name'], self.operator_a.name)
        self.assertNotIn('stop_reason_label', in_progress[0])

    def test_stopped_claim_shows_stop_reason_not_operator(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        data = self._get_board_data_as_admin()
        stopped = data['columns']['stopped']
        self.assertEqual(len(stopped), 1)
        self.assertEqual(stopped[0]['stop_reason_label'], 'Sin stock')
        self.assertNotIn('operator_name', stopped[0])

    def test_done_claim_shows_operator_name(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        # done_by_employee_id/done_date explícitos (no solo is_done):
        # _maybe_release_finished_claim() limpia claim.assigned_employee_id
        # al completarse (ver preparation_pds.py) — la identidad de
        # "quién pesó" vive en la LÍNEA, igual que para
        # get_claims_for_level1_display (done_by_employee_name).
        session.line_ids.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
            'done_by_employee_id': self.operator_a.id,
            'done_date': fields.Datetime.now(),
        })
        data = self._get_board_data_as_admin()
        done = data['columns']['done']
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0]['operator_name'], self.operator_a.name)

    def test_header_counts_match_session_progress(self):
        session = self._load_session_with_product()
        data = self._get_board_data_as_admin()
        self.assertEqual(data['total_lines'], session.total_lines)
        self.assertEqual(data['done_lines'], session.done_lines)
        self.assertEqual(data['pending_lines'], session.pending_lines)
        self.assertEqual(
            data['global_progress_pct'], session.global_progress_pct,
        )
