# -*- coding: utf-8 -*-
"""Wizard de conflicto de un solo claim por operario (plan f2, Tech
Lead, 2026-10-31) — hereda setUp de TestPreparationDayProductClaim
(operator_a/operator_b, _request_as, _load_session_with_product) para
no duplicar el fixture."""
from unittest.mock import patch

from odoo.exceptions import UserError

from .test_preparation_day_product_claim import (
    REQUEST_PATCH_TARGET,
    TestPreparationDayProductClaim,
)


class TestPreparationDayProductClaimConflictWizard(TestPreparationDayProductClaim):

    def _open_conflict_wizard(self, claim_target, claim_held, employee):
        """Reproduce el camino real: operario ya tiene claim_held En
        progreso, intenta action_assign() sobre claim_target — devuelve
        el wizard ya creado."""
        with patch(REQUEST_PATCH_TARGET, self._request_as(employee)):
            claim_held.action_assign()
            result = claim_target.action_assign()
        return self.env[
            'guapante.preparation.day.product.claim.conflict.wizard'
        ].browse(result['res_id'])

    def _two_claims(self):
        product_b = self.env['product.product'].create({
            'name': 'Producto Conflicto B', 'type': 'consu',
        })
        self._create_confirmed_order(qty=1.0, product=product_b)
        session = self._load_session_with_product()
        claim_a = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        claim_b = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == product_b.product_tmpl_id
        )
        return claim_a, claim_b

    # ── Condición 4: mensaje exacto ──

    def test_message_text_singular_and_plural(self):
        claim_held, claim_target = self._two_claims()
        wizard = self._open_conflict_wizard(
            claim_target, claim_held, self.operator_a,
        )
        self.assertEqual(
            wizard.message,
            f'Ya tienes asignado «{claim_held.product_tmpl_name}» '
            '(1 caja por pesar). Para tomar '
            f'«{claim_target.product_tmpl_name}» primero termínalo, '
            'libéralo o detenlo con un motivo.',
        )

    # ── Condición 5: "Ir a terminarlo" ──

    def test_action_go_finish_opens_level2_of_other_claim(self):
        claim_held, claim_target = self._two_claims()
        wizard = self._open_conflict_wizard(
            claim_target, claim_held, self.operator_a,
        )
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            result = wizard.action_go_finish()
        self.assertEqual(result['tag'], 'guapante_picking_level2')
        self.assertEqual(result['context']['claim_id'], claim_held.id)

    def test_action_go_finish_raises_if_other_claim_no_longer_mine(self):
        """Condición 3: si other_claim_id ya no es del operario (liberado
        por el cron, por otro tablet, etc.) mientras el wizard seguía
        abierto, "Ir a terminarlo" no tiene nada sensible que hacer —
        mensaje claro, sin efectos."""
        claim_held, claim_target = self._two_claims()
        wizard = self._open_conflict_wizard(
            claim_target, claim_held, self.operator_a,
        )
        claim_held.sudo()._release_claim()  # simula el cron de abandono

        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            with self.assertRaises(UserError):
                wizard.action_go_finish()

    # ── Condición 2: atomicidad de "Liberar y tomar este" ──

    def test_action_release_and_assign_releases_other_and_assigns_target(self):
        claim_held, claim_target = self._two_claims()
        wizard = self._open_conflict_wizard(
            claim_target, claim_held, self.operator_a,
        )
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            result = wizard.action_release_and_assign()

        self.assertEqual(result['tag'], 'guapante_picking_level2')
        claim_held.invalidate_recordset()
        claim_target.invalidate_recordset()
        self.assertFalse(
            claim_held.assigned_employee_id,
            'el que ya tenía debe quedar liberado',
        )
        self.assertEqual(
            claim_target.assigned_employee_id, self.operator_a,
            'el nuevo debe quedar asignado',
        )

    def test_action_release_and_assign_is_atomic_when_target_taken_meanwhile(self):
        """Condición 2: si otro operario se llevó el claim_target
        mientras el wizard estaba abierto, el release del que ya tenía
        TAMBIÉN se deshace — nunca se queda sin ninguno de los dos."""
        claim_held, claim_target = self._two_claims()
        wizard = self._open_conflict_wizard(
            claim_target, claim_held, self.operator_a,
        )
        # operator_b se lleva claim_target mientras el wizard de
        # operator_a sigue abierto.
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_b)):
            claim_target.action_assign()

        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            with self.assertRaises(UserError) as ctx:
                wizard.action_release_and_assign()

        self.assertIn(
            'sigue asignado a ti', str(ctx.exception),
            'el mensaje debe tranquilizar que el claim original no se '
            'perdió',
        )
        claim_held.invalidate_recordset()
        claim_target.invalidate_recordset()
        self.assertEqual(
            claim_held.assigned_employee_id, self.operator_a,
            'el release debe haberse revertido junto con el assign '
            'fallido — el operario no debe quedar sin ninguno',
        )
        self.assertEqual(claim_target.assigned_employee_id, self.operator_b)

    def test_action_release_and_assign_when_other_already_freed_just_assigns(self):
        """Condición 3, caso explícito de Tech Lead: wizard abierto, el
        otro claim se libera por el cron (o por lo que sea) ANTES del
        clic — no debe fallar raro, simplemente debe tomar el nuevo."""
        claim_held, claim_target = self._two_claims()
        wizard = self._open_conflict_wizard(
            claim_target, claim_held, self.operator_a,
        )
        claim_held.sudo()._release_claim()  # simula el cron de abandono

        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            result = wizard.action_release_and_assign()

        self.assertEqual(result['tag'], 'guapante_picking_level2')
        claim_target.invalidate_recordset()
        self.assertEqual(claim_target.assigned_employee_id, self.operator_a)

    # ── Condición 3: revalidar "Detener con motivo" ──

    def test_action_stop_other_opens_stop_wizard_for_other_claim(self):
        claim_held, claim_target = self._two_claims()
        wizard = self._open_conflict_wizard(
            claim_target, claim_held, self.operator_a,
        )
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            result = wizard.action_stop_other()
        self.assertEqual(
            result['res_model'],
            'guapante.preparation.day.product.claim.stop.wizard',
        )

    def test_action_stop_other_raises_if_other_claim_no_longer_mine(self):
        claim_held, claim_target = self._two_claims()
        wizard = self._open_conflict_wizard(
            claim_target, claim_held, self.operator_a,
        )
        claim_held.sudo()._release_claim()

        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            with self.assertRaises(UserError):
                wizard.action_stop_other()

    # ── Condición 1: el conflicto de OTRO operario sigue como UserError ──

    def test_other_operator_conflict_still_raises_plain_user_error(self):
        """El wizard es SOLO para "yo ya tengo otro" — si el conflicto es
        que OTRO operario ya tiene el claim que se quiere tomar, sigue
        siendo el UserError de siempre, sin pasar por el wizard."""
        claim_held, claim_target = self._two_claims()
        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_a)):
            claim_target.action_assign()

        with patch(REQUEST_PATCH_TARGET, self._request_as(self.operator_b)):
            with self.assertRaises(UserError) as ctx:
                claim_target.action_assign()
        self.assertIn(self.operator_a.name, str(ctx.exception))
