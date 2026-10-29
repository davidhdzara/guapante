# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.models.const_preparation import (
    set_active_prep_operator,
)
from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)

REQUEST_PATCH_TARGET_LINE = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_line.request'
)
REQUEST_PATCH_TARGET_CLAIM = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_product_claim.request'
)
REQUEST_PATCH_TARGET_PARENT = (
    'odoo.addons.ist_preparation_day.models.preparation_day.request'
)


@tagged('post_install', '-at_install')
class TestPreparationDayPickingFaseC(TestPreparationDay):
    """Nivel 2 de Picking (Fase C): expected_kg_per_unit, botón Listo
    para líneas sin repesaje, ownership en los métodos públicos de Line,
    y el aviso de cierre de toda la operación a los demás tablets.

    Líneas de historia creadas con Line.create() directo (como ya hace
    test_preparation_day_product_claim.py) en vez de pasar por una
    orden de venta real + action_load: lo que se prueba acá es la capa
    de Picking (consulta agrupada, ownership, botón Listo), no el
    cálculo de needs_weighing/estimated_kg del padre — eso ya lo cubren
    los tests de ist_preparation_day.
    """

    def setUp(self):
        super().setUp()
        self.Line = self.env['guapante.preparation.day.line']
        self.env.user.sudo().write({
            'groups_id': [(4, self.env.ref(
                'ist_preparation_day_picking.group_preparation_picking_operator'
            ).id)],
        })
        self.operator_a = self.env['hr.employee'].create({
            'name': 'Operario Fase C A',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })
        self.operator_b = self.env['hr.employee'].create({
            'name': 'Operario Fase C B',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })

    def _request_as(self, employee):
        mock_request = MagicMock()
        mock_request.session = {}
        set_active_prep_operator(mock_request.session, employee.id)
        return mock_request

    def _create_session_on(self, days_offset):
        """_create_session() del padre siempre usa self.delivery_date —
        hay una sola sesión por fecha (constraint real), así que la
        historia de OTRA sesión necesita una fecha distinta."""
        date = fields.Date.add(self.delivery_date, days=days_offset)
        return self.env['guapante.preparation.day'].create({'date': date})

    def _create_line(
        self, wizard, needs_weighing, estimated_kg,
        actual_kg=0.0, is_done=False, product=None,
    ):
        product = product or self.product_weight
        return self.Line.create({
            'wizard_id': wizard.id,
            'product_id': product.product_tmpl_id.id,
            'product_product_id': product.id,
            'needs_weighing': needs_weighing,
            'estimated_kg': estimated_kg,
            'actual_kg': actual_kg,
            'is_done': is_done,
        })

    # ── expected_kg_per_unit (punto 1 de Tech Lead) ──

    def test_refresh_uses_median_of_other_sessions_history(self):
        other_session = self._create_session_on(days_offset=-1)
        for _ in range(9):
            self._create_line(
                other_session, needs_weighing=True, estimated_kg=1.0,
                actual_kg=2.0, is_done=True,
            )
        # outlier real (ej. error de coma) — la mediana no debe moverse.
        self._create_line(
            other_session, needs_weighing=True, estimated_kg=1.0,
            actual_kg=100.0, is_done=True,
        )
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=3.0)
        session._rebuild_product_claims()
        self.assertAlmostEqual(
            session.product_claim_ids.expected_kg_per_unit, 2.0, places=3,
        )
        self.assertAlmostEqual(line.expected_kg_per_unit, 2.0, places=3)

    def test_refresh_is_zero_below_history_threshold(self):
        other_session = self._create_session_on(days_offset=-1)
        for _ in range(5):  # < MIN_WEIGHT_HISTORY_LINES (10)
            self._create_line(
                other_session, needs_weighing=True, estimated_kg=1.0,
                actual_kg=2.0, is_done=True,
            )
        session = self._create_session()
        self._create_line(session, needs_weighing=True, estimated_kg=3.0)
        session._rebuild_product_claims()
        self.assertEqual(session.product_claim_ids.expected_kg_per_unit, 0.0)

    def test_refresh_excludes_lines_of_the_session_being_loaded(self):
        """Tech Lead: lo que se pesa HOY no se cuela en su propia
        referencia — si no, un operario quedaría comparado contra pesos
        que él mismo acaba de teclear en esta misma sesión."""
        session = self._create_session()
        for _ in range(12):
            self._create_line(
                session, needs_weighing=True, estimated_kg=1.0,
                actual_kg=2.0, is_done=True,
            )
        self._create_line(session, needs_weighing=True, estimated_kg=3.0)
        session._rebuild_product_claims()
        self.assertEqual(
            session.product_claim_ids.expected_kg_per_unit, 0.0,
            "Sin historia de OTRAS sesiones todavía no debe haber alerta",
        )

    # ── action_mark_line_ready (punto 2 de Tech Lead) ──

    def test_action_mark_line_ready_marks_done_with_estimated_kg(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=4.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(guapante_picking_flow=True).action_mark_line_ready()
        self.assertTrue(line.is_done)
        self.assertEqual(line.actual_kg, 4.0)

    def test_action_mark_line_ready_raises_without_estimated_kg(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=0.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).action_mark_line_ready()
        self.assertFalse(line.is_done)

    def test_action_mark_line_ready_checks_ownership(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=4.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_b), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_b):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).action_mark_line_ready()
        self.assertFalse(line.is_done)

    # ── ownership en métodos públicos (punto 3 de Tech Lead) ──

    def test_action_save_line_weight_blocks_non_owner(self):
        """action_save_line_weight(line_id) es público y se puede llamar
        por RPC directo sin pasar antes por write() con actual_kg — el
        ownership tiene que estar ahí también."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        # skip_auto_save=True: un plain `line.actual_kg = 2.0` dispara el
        # write() completo del padre SIN guapante_picking_flow, que toma
        # la rama de Productos y marca is_done=True solo (soltando el
        # claim) — justo lo que este fixture necesita EVITAR para
        # simular "el dato ya estaba puesto" sin side effects.
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.0})
        with patch(REQUEST_PATCH_TARGET_LINE, mock_b), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_b):
            with self.assertRaises(UserError):
                session.with_context(
                    guapante_picking_flow=True,
                ).action_save_line_weight(line.id)
        self.assertFalse(line.is_done)

    def test_action_save_line_weight_allowed_by_owner(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        # skip_auto_save=True: un plain `line.actual_kg = 2.0` dispara el
        # write() completo del padre SIN guapante_picking_flow, que toma
        # la rama de Productos y marca is_done=True solo (soltando el
        # claim) — justo lo que este fixture necesita EVITAR para
        # simular "el dato ya estaba puesto" sin side effects.
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.0})
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
        self.assertTrue(line.is_done)

    def test_action_undo_line_blocks_non_owner(self):
        session = self._create_session()
        line_done = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        line_pending = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        line_done.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        self.assertEqual(
            claim.assigned_employee_id, self.operator_a,
            "line_pending sigue sin terminar: el claim no debió soltarse",
        )
        with patch(REQUEST_PATCH_TARGET_LINE, mock_b):
            with self.assertRaises(UserError):
                line_done.with_context(
                    guapante_picking_flow=True,
                ).action_undo_line()
        self.assertTrue(line_done.is_done)
        self.assertEqual(line_pending.is_done, False)

    def test_action_undo_line_allowed_by_owner(self):
        session = self._create_session()
        line_done = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        line_done.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a):
            line_done.with_context(guapante_picking_flow=True).action_undo_line()
        self.assertFalse(line_done.is_done)

    def test_action_undo_line_blocks_once_claim_has_no_owner(self):
        """Corrección de Tech Lead: una vez terminado el último
        pendiente, el claim se libera (regla de la Fase B) — pero eso NO
        abre la puerta a corregir desde Picking sin asignación. Terminado
        es solo lectura desde Picking; la corrección post-cierre la hace
        un supervisor desde la pestaña Productos."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        line.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        self.assertFalse(claim.assigned_employee_id)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).action_undo_line()
        self.assertTrue(line.is_done)

    # ── aviso de cierre de operación (punto 4 de Tech Lead) ──

    def test_write_notifies_operation_finished_on_session_completion(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        # skip_auto_save=True: un plain `line.actual_kg = 2.0` dispara el
        # write() completo del padre SIN guapante_picking_flow, que toma
        # la rama de Productos y marca is_done=True solo (soltando el
        # claim) — justo lo que este fixture necesita EVITAR para
        # simular "el dato ya estaba puesto" sin side effects.
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.0})
        BusModel = self.env.registry['bus.bus']
        with patch.object(BusModel, '_sendone') as mock_sendone, \
                patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
        self.assertEqual(session.state, 'done')
        finished_calls = [
            c for c in mock_sendone.call_args_list
            if c.args[1] == 'picking_operation_finished'
        ]
        self.assertEqual(len(finished_calls), 1)
        self.assertEqual(
            finished_calls[0].args[0], f'guapante_preparation_day-{session.id}',
        )

    def test_write_does_not_renotify_on_post_close_correction(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        # skip_auto_save=True: un plain `line.actual_kg = 2.0` dispara el
        # write() completo del padre SIN guapante_picking_flow, que toma
        # la rama de Productos y marca is_done=True solo (soltando el
        # claim) — justo lo que este fixture necesita EVITAR para
        # simular "el dato ya estaba puesto" sin side effects.
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.0})
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
        self.assertEqual(session.state, 'done')

        BusModel = self.env.registry['bus.bus']
        with patch.object(BusModel, '_sendone') as mock_sendone:
            line.with_context(skip_auto_save=True).write({'actual_kg': 3.0})
        finished_calls = [
            c for c in mock_sendone.call_args_list
            if c.args[1] == 'picking_operation_finished'
        ]
        self.assertEqual(finished_calls, [])
