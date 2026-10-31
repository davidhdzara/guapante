# -*- coding: utf-8 -*-
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.controllers.preparation_day_identification_controller import (
    PreparationDayIdentificationController,
)
from odoo.addons.ist_preparation_day.models.const_preparation import (
    CLAIM_STALE_MARGIN_SECONDS,
    PREP_OPERATOR_IDLE_TIMEOUT_SECONDS,
    set_active_prep_operator,
)
from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)

REQUEST_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_product_claim.request'
)
IDENTIFICATION_REQUEST_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day.controllers'
    '.preparation_day_identification_controller.request'
)
# Más allá del umbral de abandono (plan f1) — margen amplio para que el
# test no dependa de cuán rápido corre.
STALE_SECONDS = PREP_OPERATOR_IDLE_TIMEOUT_SECONDS + CLAIM_STALE_MARGIN_SECONDS + 30


@tagged('post_install', '-at_install')
class TestPreparationDayProductClaim(TestPreparationDay):
    """Nivel 1 de Picking (Fase B) — hereda el setUpClass y los helpers de
    TestPreparationDay (_create_confirmed_order, _create_session) para no
    duplicar el fixture de producto/partner/almacén."""

    def setUp(self):
        super().setUp()
        self.Claim = self.env['guapante.preparation.day.product.claim']
        # El usuario de test (TransactionCase) no está en el grupo de
        # Picking por defecto — se lo agrega acá para que las acciones del
        # claim no choquen con _check_picking_access() en los tests que no
        # están probando específicamente ese chequeo (test_action_assign_
        # checks_picking_group usa un NonMember aparte, a propósito).
        self.env.user.sudo().write({
            'groups_id': [(4, self.env.ref(
                'ist_preparation_day_picking.group_preparation_picking_operator'
            ).id)],
        })
        self.operator_a = self.env['hr.employee'].create({
            'name': 'Operario Claim A',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })
        self.operator_b = self.env['hr.employee'].create({
            'name': 'Operario Claim B',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })

    def _request_as(self, employee):
        """Devuelve un mock de `request` con ese operario ya identificado
        en sesión, listo para usar con patch()."""
        mock_request = MagicMock()
        mock_request.session = {}
        set_active_prep_operator(mock_request.session, employee.id)
        return mock_request

    def _load_session_with_product(self, qty=2.0, product=None):
        self._create_confirmed_order(qty=qty, product=product)
        session = self._create_session()
        session.action_load()
        return session

    # ── Ciclo de vida de los claims ──

    def test_action_load_creates_one_pending_claim_per_template(self):
        session = self._load_session_with_product()
        claims = session.product_claim_ids
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims.product_tmpl_id, self.product_weight.product_tmpl_id)
        self.assertEqual(claims.status, 'pending')
        self.assertFalse(claims.assigned_employee_id)

    def test_action_load_twice_does_not_duplicate_claims(self):
        session = self._load_session_with_product()
        session.action_load()
        claims = session.product_claim_ids
        self.assertEqual(len(claims), 1)

    def test_line_create_ensures_claim_exists_without_action_load(self):
        """Tech Lead, punto 9: el claim se asegura también al crear líneas,
        no solo en action_load()."""
        session = self._create_session()
        self.env['guapante.preparation.day.line'].create({
            'wizard_id': session.id,
            'product_id': self.product_weight.product_tmpl_id.id,
            'product_product_id': self.product_weight.id,
        })
        self.assertEqual(len(session.product_claim_ids), 1)
        self.assertEqual(session.product_claim_ids.status, 'pending')

    def test_claim_removed_when_template_loses_all_lines(self):
        session = self._load_session_with_product()
        claim_id = session.product_claim_ids.id
        session.line_ids.unlink()
        session._rebuild_product_claims()
        self.assertFalse(self.Claim.browse(claim_id).exists())

    def test_claim_with_all_lines_done_is_not_removed(self):
        """Tech Lead, punto 9: nunca se borra un claim con líneas, aunque
        estén todas is_done — ese es el estado 'done', no 'ya no existe'."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        session.line_ids.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        session._rebuild_product_claims()
        self.assertTrue(claim.exists())
        self.assertEqual(claim.status, 'done')

    # ── status computado ──

    def test_status_done_when_all_lines_done(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        session.line_ids.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        self.assertEqual(claim.status, 'done')

    def test_status_stopped_when_stop_reason_set(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        self.assertEqual(claim.status, 'stopped')
        self.assertFalse(claim.assigned_employee_id)

    def test_status_in_progress_when_assigned(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        self.assertEqual(claim.status, 'in_progress')

    def test_new_line_after_done_reopens_as_pending_without_owner(self):
        """Tech Lead, punto 4: si tras llegar a 'done' entra un pedido
        nuevo de esa plantilla (action_load agrega líneas), el claim
        vuelve a Pendiente sin dueño, no a 'En progreso' de alguien que ya
        se fue."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        session.line_ids.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        self.assertEqual(claim.status, 'done')
        self.assertFalse(claim.assigned_employee_id)

        # Nuevo pedido de la misma plantilla — simula lo que action_load
        # agregaría.
        self.env['guapante.preparation.day.line'].create({
            'wizard_id': session.id,
            'product_id': self.product_weight.product_tmpl_id.id,
            'product_product_id': self.product_weight.id,
        })
        self.assertEqual(claim.status, 'pending')
        self.assertFalse(
            claim.assigned_employee_id,
            "No debe resucitar asignado al operario que ya terminó y se fue",
        )

    # ── action_assign ──

    def test_action_assign_requires_active_operator(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with self.assertRaises(UserError):
            claim.action_assign()

    def test_action_assign_sets_owner_and_date(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        self.assertEqual(claim.assigned_employee_id, self.operator_a)
        self.assertTrue(claim.assigned_date)

    def test_action_assign_rejects_if_claim_stopped(self):
        """Tech Lead: el SELECT bloqueado tiene que mirar también
        stop_reason — un claim Detenido queda sin dueño, así que mirar
        solo assigned_employee_id dejaba que Asignarme lo tomara
        saltándose Retomar."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_b)):
            with self.assertRaises(UserError):
                claim.action_assign()
        self.assertFalse(claim.assigned_employee_id)
        self.assertEqual(claim.stop_reason, 'sin_stock')

    def test_action_assign_rejects_if_claim_done(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        session.line_ids.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        self.assertEqual(claim.status, 'done')
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            with self.assertRaises(UserError):
                claim.action_assign()

    def test_action_resume_rejects_if_claim_done(self):
        """Caso borde: todas las líneas quedaron is_done por otra vía
        (ej. Productos) mientras el claim seguía con stop_reason."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        session.line_ids.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        self.assertEqual(claim.status, 'done')
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_b)):
            with self.assertRaises(UserError):
                claim.action_resume()

    def test_action_assign_rejects_if_already_assigned_to_other(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_b)):
            with self.assertRaises(UserError) as ctx:
                claim.action_assign()
        self.assertIn(self.operator_a.name, str(ctx.exception))
        self.assertEqual(claim.assigned_employee_id, self.operator_a)

    def test_action_assign_rejects_second_claim_for_same_operator(self):
        """Tech Lead, punto 3: un operario no puede tener dos productos En
        progreso a la vez."""
        product_b = self.env['product.product'].create({
            'name': 'Producto Claim Dos',
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
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim_a.action_assign()
            with self.assertRaises(UserError):
                claim_b.action_assign()

    def test_action_assign_checks_picking_group(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        # Usuario propio sin ningún grupo (Tech Lead/QA, 2026-10-29): un
        # search(limit=1) sobre usuarios reales de este staging corre el
        # riesgo de levantar a un administrador real que bypasea ACLs y
        # esconde una regresión real — se crea el no-miembro explícitamente.
        NonMember = self.env['res.users'].sudo().create({
            'name': 'Test No Picking Group',
            'login': f'test.no.picking.group.{uuid.uuid4().hex}@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            with self.assertRaises(AccessError):
                claim.with_user(NonMember).action_assign()

    # ── action_release ──

    def test_action_release_only_by_owner(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_b)):
            with self.assertRaises(UserError):
                claim.action_release()
        self.assertEqual(claim.assigned_employee_id, self.operator_a)

    def test_action_release_clears_assignment(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_release()
        self.assertFalse(claim.assigned_employee_id)
        self.assertEqual(claim.status, 'pending')

    # ── action_stop / action_resume ──

    def test_action_stop_only_by_owner(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_b)):
            with self.assertRaises(UserError):
                claim.action_stop('sin_stock')

    def test_action_stop_invalid_reason_raises(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            with self.assertRaises(UserError):
                claim.action_stop('motivo_que_no_existe')

    def test_action_stop_posts_chatter_with_reason_and_who(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        messages_before = len(session.message_ids)
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        self.assertGreater(len(session.message_ids), messages_before)
        last_message = session.message_ids.sorted('id', reverse=True)[0]
        self.assertIn('Sin stock', last_message.body)
        self.assertIn(self.operator_a.name, last_message.body)

    def test_action_assign_does_not_post_chatter(self):
        """Tech Lead, punto 5: Asignar NO va al chatter (con 30-60
        productos por día inundaría los mensajes de pesaje)."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        messages_before = len(session.message_ids)
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        self.assertEqual(len(session.message_ids), messages_before)

    def test_action_release_does_not_post_chatter(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            messages_before = len(session.message_ids)
            claim.action_release()
        self.assertEqual(len(session.message_ids), messages_before)

    def test_action_resume_allowed_by_different_operator(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_b)):
            claim.action_resume()
        self.assertEqual(claim.assigned_employee_id, self.operator_b)
        self.assertFalse(claim.stop_reason)
        self.assertEqual(claim.status, 'in_progress')

    def test_action_resume_posts_chatter(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
            claim.action_stop('sin_stock')
        messages_before = len(session.message_ids)
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_b)):
            claim.action_resume()
        self.assertGreater(len(session.message_ids), messages_before)

    # ── finalización automática (Tech Lead, punto 4) ──

    def test_claim_released_when_last_line_finishes(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim.action_assign()
        self.assertEqual(claim.assigned_employee_id, self.operator_a)

        session.line_ids.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        self.assertFalse(
            claim.assigned_employee_id,
            "El dueño se suelta al terminar la última línea pendiente",
        )
        self.assertEqual(claim.status, 'done')

    # ── bus.bus al pesar (Tech Lead, punto 2) ──

    def test_line_write_notifies_bus_on_is_done_change(self):
        """El Nivel 1 tiene que enterarse de un pesaje hecho en el kanban
        de líneas, no solo de las acciones del propio claim — si no, los
        demás tablets siguen viendo 'En progreso' y el contador de
        pendientes viejo hasta recargar a mano."""
        session = self._load_session_with_product()
        BusModel = self.env.registry['bus.bus']
        with patch.object(BusModel, '_sendone') as mock_sendone:
            session.line_ids.with_context(skip_auto_save=True).write({
                'is_done': True, 'actual_kg': 2.0,
            })
        mock_sendone.assert_called_once_with(
            f'guapante_preparation_day-{session.id}',
            'picking_claim_updated',
            {},
        )

    def test_line_write_notifies_bus_once_per_session_not_per_line(self):
        product_b = self.env['product.product'].create({
            'name': 'Producto Claim Bus Dos Líneas',
            'type': 'consu',
        })
        self._create_confirmed_order(qty=1.0, product=product_b)
        session = self._load_session_with_product()
        self.assertGreaterEqual(len(session.line_ids), 2)

        BusModel = self.env.registry['bus.bus']
        with patch.object(BusModel, '_sendone') as mock_sendone:
            session.line_ids.with_context(skip_auto_save=True).write({
                'is_done': True, 'actual_kg': 1.0,
            })
        mock_sendone.assert_called_once()

    # ── Visibilidad entre operarios y abandono (plan f1, 2026-10-31) ──

    def _run_cron(self):
        self.Claim._cron_release_abandoned_claims()

    def test_f1_active_claim_hidden_from_other_operator(self):
        """Un claim En progreso con actividad reciente NO debe aparecer
        en absoluto para otro operario — ni la tarjeta ni el nombre."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            claim.action_assign()

        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET, mock_b):
            visible = self.Claim.get_claims_for_level1_display(session.id)
        self.assertNotIn(claim.id, [c['id'] for c in visible])

    def test_f1_stale_claim_visible_to_other_operator_before_cron(self):
        """Un claim En progreso sin actividad real desde hace más del
        umbral (operario que se fue sin cerrar sesión o perdió
        conexión) se trata como visible para TODOS, aunque la
        liberación real en base de datos todavía no haya corrido."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            claim.action_assign()
        claim.sudo().write({
            'last_activity': fields.Datetime.now() - timedelta(
                seconds=STALE_SECONDS,
            ),
        })

        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET, mock_b):
            visible = self.Claim.get_claims_for_level1_display(session.id)
        self.assertIn(claim.id, [c['id'] for c in visible])

    def test_f1_admin_sees_all_claims_with_names(self):
        """Administrador ve TODO, activo o abandonado, con el nombre de
        quien lo tiene — nunca aplica la regla de ocultamiento."""
        self.env.user.sudo().write({
            'groups_id': [(4, self.env.ref(
                'ist_preparation_day_picking.group_preparation_admin'
            ).id)],
        })
        product_b = self.env['product.product'].create({
            'name': 'Producto Claim Admin B', 'type': 'consu',
        })
        self._create_confirmed_order(qty=1.0, product=product_b)
        session = self._load_session_with_product()
        claim_active, claim_stale = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            claim_active.action_assign()
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET, mock_b):
            claim_stale.action_assign()
        claim_stale.sudo().write({
            'last_activity': fields.Datetime.now() - timedelta(
                seconds=STALE_SECONDS,
            ),
        })

        visible = self.Claim.get_claims_for_level1_display(session.id)
        visible_ids = {c['id'] for c in visible}
        self.assertIn(claim_active.id, visible_ids)
        self.assertIn(claim_stale.id, visible_ids)
        by_id = {c['id']: c for c in visible}
        self.assertEqual(
            by_id[claim_active.id]['assigned_employee_id'][0],
            self.operator_a.id,
        )
        self.assertEqual(
            by_id[claim_stale.id]['assigned_employee_id'][0],
            self.operator_b.id,
        )

    def test_f1_cerrar_releases_claim_and_reappears_for_other_operator(self):
        """"Cerrar" (controlador /clear_operator) libera los claims En
        progreso del operario — propia petición, propio commit — y el
        producto reaparece de inmediato para otro operario, sin esperar
        al cron."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            claim.action_assign()
        self.assertEqual(claim.assigned_employee_id, self.operator_a)

        close_request = MagicMock()
        close_request.env = self.env
        close_request.session = dict(mock_a.session)
        with patch(IDENTIFICATION_REQUEST_PATCH_TARGET, close_request):
            PreparationDayIdentificationController().clear_operator()

        claim.invalidate_recordset()
        self.assertFalse(claim.assigned_employee_id)
        self.assertEqual(claim.status, 'pending')

        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET, mock_b):
            visible = self.Claim.get_claims_for_level1_display(session.id)
        self.assertIn(claim.id, [c['id'] for c in visible])

    def test_f1_identification_failure_does_not_orphan_claim(self):
        """Corrección de Tech Lead sobre el primer diseño (punto A): una
        acción de escritura que falla por identificación (operario
        desactivado a mitad de turno) NO debe dejar el claim huérfano —
        la liberación nunca vive dentro de get_active_prep_operator_id,
        que corre DENTRO de la transacción de esa misma acción y puede
        verse revertida por el rollback."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            claim.action_assign()

        line = session.line_ids[:1]
        self.operator_a.active = False
        LINE_REQUEST_PATCH_TARGET = (
            'odoo.addons.ist_preparation_day_picking.models'
            '.preparation_day_line.request'
        )
        PARENT_REQUEST_PATCH_TARGET = (
            'odoo.addons.ist_preparation_day.models.preparation_day.request'
        )
        with patch(LINE_REQUEST_PATCH_TARGET, mock_a), \
                patch(PARENT_REQUEST_PATCH_TARGET, mock_a):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).write(
                    {'actual_kg': 1.5},
                )

        claim.invalidate_recordset()
        self.assertEqual(
            claim.assigned_employee_id.id, self.operator_a.id,
            'una escritura fallida por identificación no debe liberar '
            'el claim — seguiría asignado, solo que a un operario ya '
            'inválido, nunca invisible/huérfano',
        )

    def test_f1_cron_releases_only_stale_claims_not_active_ones(self):
        """El cron libera de verdad (en base de datos) el claim
        abandonado y deja una nota en el chatter de la sesión — pero no
        toca el que sigue con actividad reciente."""
        product_b = self.env['product.product'].create({
            'name': 'Producto Claim Cron B', 'type': 'consu',
        })
        self._create_confirmed_order(qty=1.0, product=product_b)
        session = self._load_session_with_product()
        claim_active, claim_stale = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            claim_active.action_assign()
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET, mock_b):
            claim_stale.action_assign()
        claim_stale.sudo().write({
            'last_activity': fields.Datetime.now() - timedelta(
                seconds=STALE_SECONDS,
            ),
        })
        messages_before = len(session.message_ids)

        self._run_cron()

        claim_active.invalidate_recordset()
        claim_stale.invalidate_recordset()
        self.assertEqual(
            claim_active.assigned_employee_id, self.operator_a,
            'un claim con actividad reciente no debe liberarse',
        )
        self.assertFalse(
            claim_stale.assigned_employee_id,
            'un claim abandonado sí debe liberarse de verdad',
        )
        self.assertEqual(claim_stale.status, 'pending')
        self.assertGreater(len(session.message_ids), messages_before)
        self.assertTrue(
            any(
                'liberado automáticamente' in (m or '')
                for m in session.message_ids.mapped('body')
            )
        )

    def test_f1_inherited_claim_without_last_activity_visible_and_released(self):
        """Corrección de Tech Lead (2026-10-31, defecto bloqueante): un
        claim En progreso HEREDADO de antes de que existiera
        last_activity (last_activity=False, assigned_date vieja — los
        que ya hay hoy en producción/staging) NO debe quedar huérfano
        invisible para siempre. _effective_last_activity hace COALESCE
        con assigned_date — debe verse como abandonado para otros
        operarios y el cron debe liberarlo de verdad."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            claim.action_assign()
        # Simula el estado heredado: sin last_activity, solo la fecha
        # vieja de asignación que ya existía antes de este plan.
        claim.sudo().write({
            'last_activity': False,
            'assigned_date': fields.Datetime.now() - timedelta(
                seconds=STALE_SECONDS,
            ),
        })

        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET, mock_b):
            visible = self.Claim.get_claims_for_level1_display(session.id)
        self.assertIn(
            claim.id, [c['id'] for c in visible],
            'un claim heredado sin last_activity debe verse como '
            'abandonado (COALESCE con assigned_date), no quedar oculto',
        )

        self._run_cron()
        claim.invalidate_recordset()
        self.assertFalse(
            claim.assigned_employee_id,
            'el cron debe liberar un claim heredado sin last_activity '
            'igual que uno con last_activity viejo',
        )

    def test_f1_stopped_claim_never_hidden_or_released_by_cron(self):
        """Corrección de Tech Lead (2026-10-31, punto 2): un claim
        Detenido es una pausa JUSTIFICADA, no abandono — nunca se
        oculta (se ve para todos, con su motivo) y el cron NUNCA lo
        libera por inactividad, ni siquiera si su write_date queda
        artificialmente viejo (defensa en profundidad: el dominio del
        cron filtra por status, no solo por assigned_employee_id)."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET, mock_a):
            claim.action_assign()
            claim.action_stop('sin_stock')
        self.assertEqual(claim.status, 'stopped')
        self.assertFalse(claim.assigned_employee_id)

        # Envejece write_date a mano (muy anterior al umbral) — ni
        # last_activity ni assigned_date alcanzan a esto porque
        # action_stop() ya los limpió; solo queda write_date.
        very_old = fields.Datetime.now() - timedelta(seconds=STALE_SECONDS * 10)
        self.env.cr.execute(
            'UPDATE guapante_preparation_day_product_claim '
            'SET write_date = %s WHERE id = %s',
            (very_old, claim.id),
        )
        claim.invalidate_recordset()

        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET, mock_b):
            visible = self.Claim.get_claims_for_level1_display(session.id)
        self.assertIn(
            claim.id, [c['id'] for c in visible],
            'un claim Detenido siempre es visible, para cualquiera',
        )

        self._run_cron()
        claim.invalidate_recordset()
        self.assertEqual(
            claim.status, 'stopped',
            'el cron nunca debe tocar un claim Detenido, sin importar '
            'cuán viejo sea su write_date',
        )
        self.assertEqual(claim.stop_reason, 'sin_stock')
