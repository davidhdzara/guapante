# -*- coding: utf-8 -*-
import re
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
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
            # product_description (David/Tech Lead, 2026-11-02): un
            # Char plano, no computado — el flujo real de action_load()
            # lo llena desde line.name; sin esto quedaba False en las
            # líneas de este helper (creadas directo, no desde una
            # orden) y rompía con TypeError cualquier assertIn contra
            # la nota de corrección/undo (que ya lo incluye).
            'product_description': product.display_name,
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
        self.assertTrue(
            line.is_qty_estimated,
            'action_mark_line_ready() acepta lo pedido sin verificar, '
            'por definición — debe marcarlo (Tech Lead, punto b.3)',
        )
        self.assertEqual(
            line.done_by_employee_id, self.operator_a,
            "El botón Listo también pasa por action_save_line_weight — "
            "debe estampar done_by_employee_id (Tech Lead, 2026-11-02)",
        )
        self.assertTrue(line.done_date)

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

    def test_write_actual_kg_blocked_when_operator_deactivated_mid_shift(self):
        """Tech Lead (2026-10-31): la validación de operario (active +
        is_guapante_prep_operator) vive ahora en get_active_prep_operator_id,
        la compuerta que usan TODAS las escrituras de Picking — no solo
        la pantalla de NIP. Si operator_a se desactiva a mitad de turno,
        incluso con su claim ya asignado, pesar debe seguir rechazándolo
        con el mismo error de "sesión expiró", no con uno de ownership."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        self.operator_a.active = False
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).write(
                    {'actual_kg': 1.5},
                )

    def test_write_actual_kg_blocked_when_operator_loses_flag_mid_shift(self):
        """Mismo caso que arriba pero quitando is_guapante_prep_operator
        en vez de archivar al empleado."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        self.operator_a.is_guapante_prep_operator = False
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).write(
                    {'actual_kg': 1.5},
                )
        self.assertFalse(line.is_done)

    def test_action_mark_line_ready_allowed_for_any_operator_with_pin(self):
        """Rediseño (David/Tech Lead, 2026-11-02): sin ownership, un
        operario con PIN vigente puede marcar Listo una línea de un
        producto asignado a OTRO — antes esto bloqueaba con UserError."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=4.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_b), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_b):
            line.with_context(guapante_picking_flow=True).action_mark_line_ready()
        self.assertTrue(line.is_done)

    # ── Productos sin pesaje: kg directo y unidades (punto b, Tech
    # Lead/David, 2026-10-29) ──

    def test_qty_uom_label_kg_for_weight_product(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=4.0)
        self.assertEqual(line.qty_uom_label, 'kg')

    def test_qty_uom_label_und_for_unit_product(self):
        session = self._create_session()
        line = self._create_line(
            session, needs_weighing=False, estimated_kg=3.0,
            product=self.product_unit,
        )
        self.assertEqual(line.qty_uom_label, 'und')

    def test_qty_uom_label_false_for_unsupported_uom(self):
        """Datos reales (staging y producción, 2026-10-29): no existe
        hoy ningún producto vendible con UoM de peso/unidad NO-referencia
        (ej. Docenas, factor 12) — pero si alguna vez aparece, no debe
        asumirse kg ni unidades a ciegas (David: sin defaults
        silenciosos)."""
        session = self._create_session()
        dozen_uom = self.env.ref('uom.product_uom_dozen')
        product_dozen = self.env['product.product'].create({
            'name': 'Producto Docena Test',
            'type': 'consu',
            'uom_id': dozen_uom.id,
            'uom_po_id': dozen_uom.id,
        })
        line = self._create_line(
            session, needs_weighing=False, estimated_kg=2.0,
            product=product_dozen,
        )
        self.assertFalse(line.qty_uom_label)

    def test_write_actual_kg_raises_for_unsupported_uom(self):
        session = self._create_session()
        dozen_uom = self.env.ref('uom.product_uom_dozen')
        product_dozen = self.env['product.product'].create({
            'name': 'Producto Docena Test 2',
            'type': 'consu',
            'uom_id': dozen_uom.id,
            'uom_po_id': dozen_uom.id,
        })
        line = self._create_line(
            session, needs_weighing=False, estimated_kg=2.0,
            product=product_dozen,
        )
        claim = session.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == line.product_id
        )
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            with self.assertRaises(UserError):
                line.with_context(
                    guapante_picking_flow=True, guapante_qty_estimated=True,
                ).write({'actual_kg': 2.0})
        self.assertFalse(line.is_done)

    def test_write_actual_kg_unedited_marks_estimated_kg_direct(self):
        """Kg pedido directo (is_weight=True, needs_weighing=False) — el
        operario confirma sin editar el valor precargado."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=4.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(
                guapante_picking_flow=True, guapante_qty_estimated=True,
            ).write({'actual_kg': 4.0})
        self.assertTrue(line.is_qty_estimated)
        self.assertEqual(line.actual_kg, 4.0)
        self.assertTrue(line.is_done)

    def test_write_actual_kg_edited_marks_not_estimated_kg_direct(self):
        """Mismo caso pero el operario edita el valor — debe quedar en
        False y con el valor real, aunque sea MENOR que lo pedido (regla
        de David: el servidor no bloquea despachar menos, solo la UI
        pregunta antes de llegar aquí)."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=4.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(
                guapante_picking_flow=True, guapante_qty_estimated=False,
            ).write({'actual_kg': 3.2})
        self.assertFalse(line.is_qty_estimated)
        self.assertEqual(line.actual_kg, 3.2)
        self.assertTrue(line.is_done)

    def test_write_actual_kg_without_qty_estimated_context_defaults_false(self):
        """Corrección #7 (David, 2026-10-31): el input de Nivel 2 ya no
        precarga ni envía guapante_qty_estimated — onConfirmWeight manda
        actual_kg solo. Confirma que, sin esa clave en el contexto en
        absoluto (no False explícito, AUSENTE), is_qty_estimated cae en
        False igual — action_mark_line_ready sigue siendo el único
        camino que la deja en True."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=4.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(guapante_picking_flow=True).write(
                {'actual_kg': 4.0},
            )
        self.assertFalse(line.is_qty_estimated)
        self.assertEqual(line.actual_kg, 4.0)
        self.assertTrue(line.is_done)

    def test_write_actual_kg_unedited_marks_estimated_units(self):
        """Mismo patrón, producto por unidad (is_weight=False)."""
        session = self._create_session()
        line = self._create_line(
            session, needs_weighing=False, estimated_kg=3.0,
            product=self.product_unit,
        )
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(
                guapante_picking_flow=True, guapante_qty_estimated=True,
            ).write({'actual_kg': 3.0})
        self.assertTrue(line.is_qty_estimated)
        self.assertEqual(line.actual_kg, 3.0)

    def test_write_actual_kg_edited_marks_not_estimated_units(self):
        session = self._create_session()
        line = self._create_line(
            session, needs_weighing=False, estimated_kg=3.0,
            product=self.product_unit,
        )
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(
                guapante_picking_flow=True, guapante_qty_estimated=False,
            ).write({'actual_kg': 5.0})
        self.assertFalse(line.is_qty_estimated)
        self.assertEqual(line.actual_kg, 5.0)

    def test_needs_weighing_line_never_marks_estimated(self):
        """Blindaje (Tech Lead, punto b.1/3): aunque llegue
        guapante_qty_estimated=True por error en una línea que sí
        necesita pesaje real, nunca debe marcarse — ese contexto es
        solo para los casos sin pesaje."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(
                guapante_picking_flow=True, guapante_qty_estimated=True,
            ).write({'actual_kg': 2.0})
        self.assertFalse(
            line.is_qty_estimated,
            'needs_weighing=True nunca debe marcarse, sin importar el contexto',
        )
        self.assertTrue(line.is_done)

    def test_action_undo_line_resets_is_qty_estimated(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=4.0)
        # Segunda línea pendiente del mismo producto (mismo patrón que
        # test_action_undo_line_allowed_by_owner): sin ella, al terminar
        # `line` el claim se libera (Fase B, última pendiente) y el
        # undo posterior ya no pasaría el chequeo de ownership — lo que
        # este test necesita aislar es el reset del campo, no ese otro
        # comportamiento (ya cubierto en sus propios tests).
        self._create_line(session, needs_weighing=False, estimated_kg=1.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(
                guapante_picking_flow=True, guapante_qty_estimated=True,
            ).write({'actual_kg': 4.0})
        self.assertTrue(line.is_qty_estimated)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a):
            line.with_context(guapante_picking_flow=True).action_undo_line()
        self.assertFalse(
            line.is_qty_estimated,
            'Sin caja despachada no hay "lo pedido aceptado" que señalar',
        )
        self.assertEqual(line.actual_kg, 0.0)

    def test_write_actual_kg_unedited_double_call_registers_once(self):
        """Doble Enter/doble clic del camino "confirmar sin editar" (kg
        directo, sin pesaje) — sin ownership (David/Tech Lead,
        2026-11-02), la segunda llamada ya no se bloquea con UserError:
        new_kg == old_kg no matchea ni la rama de corrección
        (new_kg != old_kg) ni la de undo (new_kg == 0) en write() de
        CORE, así que es un no-op explícito por el propio dispatch, no
        una excepción."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=False, estimated_kg=4.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        Summary = session.summary_ids.filtered(
            lambda s: s.product_id == line.product_product_id
        )
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(
                guapante_picking_flow=True, guapante_qty_estimated=True,
            ).write({'actual_kg': 4.0})
            kg_after_first = Summary.total_done_kg
            # Segunda llamada con el mismo valor — simula el doble
            # Enter/doble clic alcanzando al servidor.
            line.with_context(
                guapante_picking_flow=True, guapante_qty_estimated=True,
            ).write({'actual_kg': 4.0})
        self.assertEqual(Summary.total_done_kg, kg_after_first)
        self.assertTrue(line.is_qty_estimated)
        self.assertEqual(line.actual_kg, 4.0)

    # ── sin ownership en métodos públicos (rediseño David/Tech Lead,
    # 2026-11-02 — antes bloqueaban por claim, ahora solo exigen PIN
    # vigente, para cualquier operario) ──

    def test_action_save_line_weight_allowed_for_any_operator_with_pin(self):
        """action_save_line_weight(line_id) es público y se puede llamar
        por RPC directo sin pasar antes por write() con actual_kg —
        antes bloqueaba si el claim no era de quien pesa; ahora cualquier
        operario con PIN vigente puede, sea o no el dueño."""
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
            session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
        self.assertTrue(line.is_done)

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

    def test_action_save_line_weight_double_call_registers_once(self):
        """Peso Nivel 2 (Tech Lead, 2026-10-29): aunque un doble Enter o
        doble clic en el cliente llegue a disparar dos RPC al servidor
        en secuencia, el guardado queda registrado una sola vez. Sin
        ownership (David/Tech Lead, 2026-11-02), la segunda llamada ya
        no se bloquea con UserError — el propio guard de
        action_save_line_weight() (`if ... Line.is_done ...: return
        False`) la vuelve no-op, línea ya is_done=True tras la
        primera."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.0})
        Summary = session.summary_ids.filtered(
            lambda s: s.product_id == line.product_product_id
        )
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
            logs_after_first = self.env['guapante.picking.log'].search_count([
                ('wizard_id', '=', session.id),
            ])
            kg_after_first = Summary.total_done_kg
            # Segunda llamada con el mismo line_id — simula el doble
            # Enter/doble clic alcanzando al servidor.
            second_result = session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
        self.assertFalse(second_result)
        self.assertEqual(
            self.env['guapante.picking.log'].search_count([
                ('wizard_id', '=', session.id),
            ]),
            logs_after_first,
            'La segunda llamada no debe crear un segundo registro de log',
        )
        self.assertEqual(
            Summary.total_done_kg, kg_after_first,
            'La segunda llamada no debe sumar el peso dos veces',
        )
        self.assertTrue(line.is_done)
        self.assertEqual(line.actual_kg, 2.0)

    def test_write_actual_kg_double_call_registers_once(self):
        """Mismo caso que arriba pero por el camino REAL que usa la UI de
        Nivel 2: `orm.write(..., {'actual_kg': value}, {guapante_picking_
        flow: True})` — no action_save_line_weight() directo (Tech Lead,
        2026-10-29, sobre el test anterior: ese pega al método, este
        pega al write() real). Sin ownership (David/Tech Lead,
        2026-11-02): la segunda llamada ya no se bloquea con UserError —
        new_kg == old_kg en write() de CORE no matchea ni corrección ni
        undo, así que es no-op por dispatch, sin tocar el log ni
        total_done_kg."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        Summary = session.summary_ids.filtered(
            lambda s: s.product_id == line.product_product_id
        )
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(guapante_picking_flow=True).write({'actual_kg': 2.0})
            logs_after_first = self.env['guapante.picking.log'].search_count([
                ('wizard_id', '=', session.id),
            ])
            kg_after_first = Summary.total_done_kg
            # Segunda llamada por el mismo camino real — simula el doble
            # Enter/doble clic de la UI alcanzando al servidor.
            line.with_context(
                guapante_picking_flow=True,
            ).write({'actual_kg': 2.0})
        self.assertEqual(
            self.env['guapante.picking.log'].search_count([
                ('wizard_id', '=', session.id),
            ]),
            logs_after_first,
            'La segunda llamada no debe crear un segundo registro de log',
        )
        self.assertEqual(
            Summary.total_done_kg, kg_after_first,
            'La segunda llamada no debe sumar el peso dos veces',
        )
        self.assertTrue(line.is_done)
        self.assertEqual(line.actual_kg, 2.0)

    def test_action_undo_line_allowed_for_non_owner(self):
        """Rediseño (David/Tech Lead, 2026-11-02): sin ownership, un
        operario con PIN vigente puede devolver a Pendiente una línea
        de un producto asignado a OTRO — antes esto bloqueaba.

        Transitorio: E2 va a quitarle a Picking la capacidad de
        deshacer por completo ("sin deshacer" en el rediseño) — cuando
        eso aterrice, este test deja de tener sentido tal cual (ya no
        habrá acción_undo_line alcanzable desde el tablet para nadie,
        dueño o no) y hay que reescribirlo o borrarlo entonces, no
        ahora."""
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
        with patch(REQUEST_PATCH_TARGET_LINE, mock_b):
            line_done.with_context(
                guapante_picking_flow=True,
            ).action_undo_line()
        self.assertFalse(line_done.is_done)
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

    def test_action_undo_line_allowed_once_claim_has_no_owner(self):
        """Rediseño (David/Tech Lead, 2026-11-02): antes, un claim sin
        dueño (liberado al terminar su última caja) bloqueaba
        action_undo_line desde Picking por completo — ya no: solo
        exige PIN vigente, sin importar si el claim tiene dueño.

        Transitorio, mismo aviso que test_action_undo_line_allowed_
        for_non_owner — E2 quita esta capacidad del tablet por completo."""
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
            line.with_context(guapante_picking_flow=True).action_undo_line()
        self.assertFalse(line.is_done)

    # ── concurrencia barata y guard de sesión cerrada para el operario
    # (rediseño, David/Tech Lead, 2026-11-02) ──

    def test_write_actual_kg_already_done_by_lock_time_is_treated_as_correction(self):
        """Lo que garantiza el SELECT ... FOR UPDATE de write() (CORE):
        si para cuando esta escritura toma el lock de la línea ya está
        Terminada (otro operario la pesó mientras esta esperaba), se
        reevalúa is_done YA bajo el lock y se trata como corrección —
        nunca como un segundo primer guardado. No se puede forzar una
        carrera real de dos transacciones dentro de un solo test de
        Odoo; esto verifica el resultado observable que el lock
        garantiza: encontrar la línea ya hecha al tomarla.

        Segundo producto pendiente: sin él, terminar la única línea
        cierra la sesión y la "corrección" de operator_b chocaría con
        el guard de sesión cerrada en vez de probar lo que este test
        quiere probar — eso se prueba aparte."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        self._create_line(
            session, needs_weighing=True, estimated_kg=1.0,
            product=self.product_unit,
        )
        mock_a = self._request_as(self.operator_a)
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(guapante_picking_flow=True).write({'actual_kg': 2.0})
        self.assertTrue(line.is_done)
        messages_before = len(session.message_ids)

        with patch(REQUEST_PATCH_TARGET_LINE, mock_b), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_b):
            line.with_context(guapante_picking_flow=True).write({'actual_kg': 2.6})

        self.assertTrue(line.is_done, 'sigue Terminada, nunca se reabrió')
        self.assertEqual(line.actual_kg, 2.6)
        note = session.message_ids.sorted('id', reverse=True)[0]
        self.assertIn('Corregido', note.body)
        self.assertGreater(len(session.message_ids), messages_before)

    def test_write_weight_correction_blocked_for_operator_when_session_is_done(self):
        """David/Tech Lead, 2026-11-02: el operario NO corrige pesos con
        la sesión cerrada — solo un administrador, desde Preparación o
        reabriendo la sesión. Backend sin guapante_picking_flow sigue
        permitido (ver test_write_weight_correction_allowed_when_
        session_is_done en este mismo archivo, de (1))."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(guapante_picking_flow=True).write({'actual_kg': 2.0})
        self.assertEqual(session.state, 'done', 'setup: único producto terminado cierra la sesión')
        messages_before = len(session.message_ids)

        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).write({'actual_kg': 2.6})
        # El guard lanza ANTES de _register_weight_correction() — nunca
        # llega a sincronizar stock ni a postear su nota "Corregido".
        # No se verifica actual_kg directo: ya quedó escrito por
        # super().write() antes del raise (mismo caso ya aceptado en
        # test_write_actual_kg_blocked_when_operator_loses_flag_mid_
        # shift, que tampoco lo verifica por el mismo motivo).
        self.assertEqual(len(session.message_ids), messages_before)

    # ── trazabilidad cruzada: pesar/corregir un producto asignado a
    # OTRO (rediseño, David/Tech Lead, 2026-11-02) ──

    def test_write_actual_kg_posts_cross_operator_note_when_actor_is_not_owner(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        messages_before = len(session.message_ids)

        with patch(REQUEST_PATCH_TARGET_LINE, mock_b), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_b):
            line.with_context(guapante_picking_flow=True).write({'actual_kg': 2.0})

        self.assertGreater(len(session.message_ids), messages_before)
        cross_notes = session.message_ids.filtered(
            lambda m: 'estaba asignado a' in (m.body or '')
        )
        self.assertEqual(len(cross_notes), 1)
        self.assertIn('pesó', cross_notes.body)
        self.assertIn(self.operator_b.name, cross_notes.body)
        self.assertIn(self.operator_a.name, cross_notes.body)
        self.assertIn(line.product_description, cross_notes.body)
        self.assertIn(str(line.daily_sequence), cross_notes.body)

    def test_write_actual_kg_no_cross_operator_note_when_actor_is_owner(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()

        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            line.with_context(guapante_picking_flow=True).write({'actual_kg': 2.0})

        cross_notes = session.message_ids.filtered(
            lambda m: 'estaba asignado a' in (m.body or '')
        )
        self.assertFalse(cross_notes)

    # ── nota automática "Corregido" y guard de sesión cerrada (M-1,
    # David/Tech Lead, 2026-11-02) ──

    def test_action_undo_line_posts_note_from_tablet_with_operator_and_weight(self):
        """Segunda línea pendiente del MISMO producto (David/Tech Lead,
        2026-11-02, hallazgo al correr la batería completa): sin ella,
        terminar la única línea suelta el claim (_maybe_release_
        finished_claim) antes de llegar al undo, y _check_picking_
        ownership del tablet lo bloquearía por falta de dueño — no es
        lo que este test quiere probar (eso ya lo cubre
        test_action_undo_line_blocks_once_claim_has_no_owner)."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        line.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.5,
        })
        messages_before = len(session.message_ids)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a):
            line.with_context(guapante_picking_flow=True).action_undo_line()
        self.assertGreater(len(session.message_ids), messages_before)
        note = session.message_ids.sorted('id', reverse=True)[0]
        self.assertIn('Corregido', note.body)
        self.assertIn(line.product_description, note.body)
        self.assertIn(str(line.daily_sequence), note.body)
        self.assertIn(self.operator_a.name, note.body)
        self.assertIn('2.5', note.body)

    def test_action_undo_line_posts_note_from_backend_with_odoo_user_as_actor(self):
        """Mismo código para el botón nuevo de la lista de líneas y el
        viejo del wizard de Productos — los dos llaman action_undo_line
        sin guapante_picking_flow en contexto, así que un solo test
        cubre a ambos del lado del servidor."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        line.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 3.0,
        })
        messages_before = len(session.message_ids)
        line.action_undo_line()
        self.assertGreater(len(session.message_ids), messages_before)
        note = session.message_ids.sorted('id', reverse=True)[0]
        self.assertIn('Corregido', note.body)
        self.assertIn(self.env.user.name, note.body)
        self.assertIn('3.0', note.body)
        self.assertFalse(line.is_done)

    def test_action_undo_line_does_not_duplicate_note_on_second_call(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        line.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        line.action_undo_line()
        correction_notes = session.message_ids.filtered(
            lambda m: 'Corregido' in (m.body or '')
        )
        self.assertEqual(len(correction_notes), 1)
        messages_before = len(session.message_ids)
        # Segunda llamada: la línea ya no está is_done, ToUndo queda
        # vacío — ni nota ni error, simple no-op (doble clic/RPC
        # repetido).
        line.action_undo_line()
        self.assertEqual(len(session.message_ids), messages_before)

    def test_action_undo_line_blocks_from_backend_when_session_is_done(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        # Mismo camino de test_write_notifies_operation_finished_on_
        # session_completion para llegar a session.state == 'done' de
        # verdad (skip_auto_save solo deja puesto actual_kg; hace falta
        # action_save_line_weight() para disparar el cierre).
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.0})
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
        self.assertEqual(session.state, 'done', 'setup: único producto terminado cierra la sesión')
        with self.assertRaises(UserError):
            line.action_undo_line()
        self.assertTrue(line.is_done, 'el guard bloquea antes de tocar nada')

    def test_action_undo_line_blocks_from_tablet_when_session_is_forced_done(self):
        """Caso defensivo, no el camino natural: con el flujo normal,
        una sesión `done` implica TODOS los claims liberados (sin
        dueño) — eso ya bloquea al operario con el error de ownership
        de test_action_undo_line_blocks_once_claim_has_no_owner, antes
        de llegar a este guard. Acá se fuerza `state='done'` a mano
        mientras el claim sigue asignado, para probar que el guard de
        sesión cerrada protege el método en sí (defensa en
        profundidad), no solo porque la ruta normal nunca lo deja
        llegar tan lejos."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        line.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })
        self.assertEqual(claim.assigned_employee_id, self.operator_a)
        session.sudo().write({'state': 'done'})
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).action_undo_line()
        self.assertTrue(line.is_done)

    # ── edición inline de admin disparada vía write(), no por llamada
    # directa a action_undo_line() (M-1 v2, David/Tech Lead, 2026-11-02) ──

    def test_write_zero_from_backend_reverts_and_posts_note(self):
        """Admin pone en 0 el peso de una línea Terminada desde la lista
        de líneas (edición inline, sin guapante_picking_flow en
        contexto) — mismo efecto y nota que llamar action_undo_line()
        directo, pero disparado por write() desde el dispatch de CORE."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        line.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.5,
        })
        messages_before = len(session.message_ids)

        line.write({'actual_kg': 0})

        self.assertFalse(line.is_done)
        self.assertEqual(line.actual_kg, 0.0)
        self.assertFalse(line.done_by_employee_id)
        self.assertFalse(line.done_date)
        self.assertGreater(len(session.message_ids), messages_before)
        note = session.message_ids.sorted('id', reverse=True)[0]
        self.assertIn('Corregido', note.body)
        self.assertIn(line.product_description, note.body)
        self.assertIn(str(line.daily_sequence), note.body)
        self.assertIn(self.env.user.name, note.body)

    def test_write_zero_from_backend_blocked_when_session_is_done(self):
        """Mismo guard de sesión cerrada que action_undo_line(), ahora
        disparado por la edición inline (write con actual_kg=0) en vez
        de por una llamada directa al método."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.0})
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
        self.assertEqual(session.state, 'done', 'setup: único producto terminado cierra la sesión')

        with self.assertRaises(UserError):
            line.write({'actual_kg': 0})
        self.assertTrue(line.is_done, 'el guard bloquea antes de revertir is_done/done_by/done_date')
        self.assertTrue(line.done_by_employee_id)
        self.assertTrue(line.done_date)

    def test_write_weight_correction_allowed_when_session_is_done(self):
        """A diferencia de poner el peso en 0, corregirlo a otro valor
        > 0 SÍ se permite con la sesión cerrada (no reabre nada, solo
        re-sincroniza stock/resumen) — y la nota ya trae el nombre real
        del actor, el producto y ambos valores (antes mostraba un texto
        genérico 'operario con PIN activo')."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.0})
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
        self.assertEqual(session.state, 'done')
        messages_before = len(session.message_ids)

        line.write({'actual_kg': 2.8})

        self.assertTrue(line.is_done, 'corregir peso no reabre la línea')
        self.assertEqual(line.actual_kg, 2.8)
        self.assertGreater(len(session.message_ids), messages_before)
        note = session.message_ids.sorted('id', reverse=True)[0]
        self.assertIn('Corregido', note.body)
        self.assertIn(line.product_description, note.body)
        self.assertIn(str(line.daily_sequence), note.body)
        self.assertIn(self.env.user.name, note.body)
        self.assertIn('2.000', note.body)
        self.assertIn('2.800', note.body)

    def test_write_zero_on_done_line_does_not_recurse(self):
        """La escritura interna de action_undo_line() (skip_auto_save)
        no debe reentrar al dispatch de write() — si recurriera,
        quedaría una segunda nota 'Corregido' (o un RecursionError).
        Una sola nota y un solo ciclo de reversa prueban que
        skip_auto_save corta la cadena donde debe."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        line.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.0,
        })

        line.write({'actual_kg': 0})

        correction_notes = session.message_ids.filtered(
            lambda m: 'Corregido' in (m.body or '')
        )
        self.assertEqual(len(correction_notes), 1)
        self.assertFalse(line.is_done)
        self.assertEqual(line.actual_kg, 0.0)

    # ── edición inline de admin, casilla "Terminado" (E4, David/Tech
    # Lead, 2026-11-02) — mismo dispatch de CORE (track_done), ahora
    # disparado por write({'is_done': ...}) en vez de actual_kg ──

    def test_write_is_done_true_marks_done_like_weighing(self):
        """Marcar la casilla Terminado (sin tocar el peso) con un peso ya
        puesto > 0 debe tener el mismo efecto que pesar desde cero:
        reusa _register_weight_from_productos_tab() entero (estampa
        done_by/done_date, sincroniza stock/resumen)."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.5})
        self.assertFalse(line.is_done, 'setup: peso puesto, aún no Terminado')

        line.write({'is_done': True})

        self.assertTrue(line.is_done)
        self.assertTrue(
            line.done_date,
            'done_by_employee_id depende de que env.user tenga un '
            'empleado vinculado (ver test_register_weight_from_'
            'productos_tab_stamps_date_without_employee en CORE) — '
            'no se fija en los fixtures de esta clase, solo done_date.',
        )

    def test_write_is_done_true_with_zero_weight_raises(self):
        """Marcar Terminado sin un peso registrado (actual_kg<=0) debe
        dar un UserError claro, nombrando el producto y la caja — nunca
        un Terminado silencioso de un peso que no existe."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        self.assertEqual(line.actual_kg, 0.0, 'setup: sin peso puesto')

        with self.assertRaises(UserError):
            line.write({'is_done': True})
        self.assertFalse(line.is_done, 'el guard bloquea antes de marcar nada')

    def test_write_is_done_false_on_done_line_reverts_via_action_undo_line(self):
        """Desmarcar Terminado (sin tocar el peso) debe tener el mismo
        efecto que action_undo_line(): vuelve a Pendiente, limpia
        done_by/done_date, el peso y el stock, y posta la misma nota."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        line.with_context(skip_auto_save=True).write({
            'is_done': True, 'actual_kg': 2.5,
        })
        messages_before = len(session.message_ids)

        line.write({'is_done': False})

        self.assertFalse(line.is_done)
        self.assertEqual(line.actual_kg, 0.0)
        self.assertFalse(line.done_by_employee_id)
        self.assertFalse(line.done_date)
        self.assertGreater(len(session.message_ids), messages_before)
        note = session.message_ids.sorted('id', reverse=True)[0]
        self.assertIn('Corregido', note.body)

    def test_write_is_done_false_blocked_when_session_is_done(self):
        """Mismo guard de sesión cerrada que poner el peso en 0 — ahora
        disparado por desmarcar la casilla Terminado."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.0})
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock_a):
            session.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)
        self.assertEqual(session.state, 'done', 'setup: único producto terminado cierra la sesión')

        with self.assertRaises(UserError):
            line.write({'is_done': False})
        self.assertTrue(line.is_done, 'el guard bloquea antes de revertir nada')
        self.assertTrue(line.done_by_employee_id)
        self.assertTrue(line.done_date)

    def test_write_is_done_and_actual_kg_together_treated_as_weighing(self):
        """Marcar la casilla Terminado Y escribir un peso nuevo en la
        misma fila (mismo vals) no debe pasar por track_done — el
        camino de actual_kg (track_kg) ya decide todo solo con el peso,
        is_done termina correcto sin que este bloque intervenga. Sin
        esta exclusión mutua, el guard de 'peso > 0' de track_done
        podría disparar sobre un peso viejo (0) antes de que
        super().write() ponga el nuevo."""
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        self.assertEqual(line.actual_kg, 0.0, 'setup: sin peso puesto')

        line.write({'actual_kg': 2.5, 'is_done': True})

        self.assertTrue(line.is_done)
        self.assertEqual(line.actual_kg, 2.5)
        self.assertTrue(line.done_date)

    def test_is_done_editable_only_for_admin_in_line_list(self):
        """Mismo mecanismo que actual_kg (ver test_actual_kg_editable_
        only_for_admin_in_line_list): dos nodos del mismo campo con
        groups complementarios, get_view() elimina del arch el que el
        usuario no puede ver."""
        View = self.env.ref(
            'ist_preparation_day_picking.view_preparation_day_line_list_picking'
        )
        admin_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin'
        )
        def is_done_nodes(arch):
            return re.findall(r'<field[^>]*name="is_done"[^>]*/>', arch)

        self.env.user.sudo().write({'groups_id': [(3, admin_group.id)]})
        without_admin = self.env['guapante.preparation.day.line'].get_view(
            view_id=View.id, view_type='list',
        )['arch']
        nodes = is_done_nodes(without_admin)
        self.assertEqual(
            len(nodes), 1,
            'sin el grupo admin debe quedar un único nodo is_done (el '
            'de solo lectura) — el editable se elimina del arch',
        )
        self.assertIn('readonly="1"', nodes[0])

        self.env.user.sudo().write({'groups_id': [(4, admin_group.id)]})
        with_admin = self.env['guapante.preparation.day.line'].get_view(
            view_id=View.id, view_type='list',
        )['arch']
        nodes = is_done_nodes(with_admin)
        self.assertEqual(
            len(nodes), 1,
            'con el grupo admin debe quedar un único nodo is_done (el '
            'editable) — el de solo lectura se elimina del arch',
        )
        self.assertNotIn('readonly="1"', nodes[0])

    # ── Reabrir sesión, solo admin (E5, David/Tech Lead, 2026-11-02) ──

    def test_action_reopen_blocked_without_admin_group(self):
        """Sin group_preparation_admin, action_reopen() debe rechazar
        con AccessError antes de llegar a super() — defensa en
        profundidad, el botón del form ya queda oculto para este caso
        (ver test de 'groups' en la vista, mismo patrón que is_done/
        actual_kg)."""
        session = self._create_session()
        self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        session.action_mark_done()
        admin_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin'
        )
        self.env.user.sudo().write({'groups_id': [(3, admin_group.id)]})

        with self.assertRaises(AccessError):
            session.action_reopen()
        self.assertEqual(session.state, 'done', 'el guard bloquea antes de tocar nada')

    def test_action_reopen_allowed_for_admin(self):
        session = self._create_session()
        self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        session.action_mark_done()
        self.assertTrue(session.date_done)
        admin_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin'
        )
        self.env.user.sudo().write({'groups_id': [(4, admin_group.id)]})

        session.action_reopen()

        self.assertEqual(session.state, 'loaded')
        self.assertFalse(session.date_done)

    def test_actual_kg_editable_only_for_admin_in_line_list(self):
        """v2 (David/Tech Lead, 2026-11-02): ya no hay botón "Corregir" —
        el peso se edita inline, solo para group_preparation_admin. Dos
        nodos del mismo campo con groups complementarios (uno negado):
        get_view() resuelve 'groups' en el servidor y elimina del arch
        el nodo que el usuario no puede ver (mismo mecanismo que probaba
        el test anterior del botón, ahora aplicado al campo)."""
        View = self.env.ref(
            'ist_preparation_day_picking.view_preparation_day_line_list_picking'
        )
        admin_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin'
        )
        def actual_kg_nodes(arch):
            return re.findall(r'<field[^>]*name="actual_kg"[^>]*/>', arch)

        self.env.user.sudo().write({'groups_id': [(3, admin_group.id)]})
        without_admin = self.env['guapante.preparation.day.line'].get_view(
            view_id=View.id, view_type='list',
        )['arch']
        nodes = actual_kg_nodes(without_admin)
        self.assertEqual(
            len(nodes), 1,
            'sin el grupo admin debe quedar un único nodo actual_kg (el '
            'de solo lectura) — el editable se elimina del arch',
        )
        self.assertIn('readonly="1"', nodes[0])

        self.env.user.sudo().write({'groups_id': [(4, admin_group.id)]})
        with_admin = self.env['guapante.preparation.day.line'].get_view(
            view_id=View.id, view_type='list',
        )['arch']
        nodes = actual_kg_nodes(with_admin)
        self.assertEqual(
            len(nodes), 1,
            'con el grupo admin debe quedar un único nodo actual_kg (el '
            'editable) — el de solo lectura se elimina del arch',
        )
        self.assertNotIn('readonly="1"', nodes[0])

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

    # ── (4b) nota resumen "Terminado" en el chatter (Tech Lead/David,
    # 2026-11-02): inicio/fin con hora y reparto de líneas por operario.
    # David descartó la nota al tomar (ruido, ver test de abajo) — toda
    # la info nueva vive en esta única nota de cierre. ──

    def _weigh_as(self, line, employee, kg):
        line.with_context(skip_auto_save=True).write({'actual_kg': kg})
        mock = self._request_as(employee)
        with patch(REQUEST_PATCH_TARGET_LINE, mock), \
                patch(REQUEST_PATCH_TARGET_PARENT, mock):
            line.wizard_id.with_context(
                guapante_picking_flow=True,
            ).action_save_line_weight(line.id)

    def test_action_assign_does_not_post_tomado_chatter(self):
        """David (2026-11-02): tomar un producto nunca antes tomado NO
        deja nota — es ruido, la tarjeta de L1 ya muestra "Asignado a"
        y quien lo toma queda registrado al pesar, en la nota
        Terminado."""
        session = self._create_session()
        self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        messages_before = len(session.message_ids)
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_assign()
        self.assertEqual(len(session.message_ids), messages_before)

    def test_terminado_chatter_shows_breakdown_and_different_start_end(self):
        session = self._create_session()
        lines_a = [
            self._create_line(session, needs_weighing=True, estimated_kg=1.0)
            for _ in range(3)
        ]
        line_b = self._create_line(session, needs_weighing=True, estimated_kg=1.0)
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_assign()
        for line in lines_a:
            self._weigh_as(line, self.operator_a, 1.0)
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_release()
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_b)):
            claim.action_assign()
        self._weigh_as(line_b, self.operator_b, 1.0)

        # filtered, no el último mensaje a secas (E5, 2026-11-02):
        # terminar la última línea cierra la sesión, que ahora deja su
        # propia nota de cierre DESPUÉS de esta — ver action_mark_done().
        terminado = session.message_ids.filtered(
            lambda m: 'Terminado' in (m.body or '')
        ).sorted('id', reverse=True)[0]
        self.assertIn('Terminado', terminado.body)
        self.assertIn(f'inició {self.operator_a.name}', terminado.body)
        self.assertIn(f'terminó {self.operator_b.name}', terminado.body)
        self.assertIn(f'{self.operator_a.name} (3 líneas)', terminado.body)
        self.assertIn(f'{self.operator_b.name} (1 línea)', terminado.body)
        self.assertFalse(claim.assigned_employee_id)

    def test_terminado_chatter_does_not_repeat_name_for_single_operator(self):
        session = self._create_session()
        lines = [
            self._create_line(session, needs_weighing=True, estimated_kg=1.0)
            for _ in range(2)
        ]
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_assign()
        for line in lines:
            self._weigh_as(line, self.operator_a, 1.0)

        # filtered, no el último mensaje a secas (E5, 2026-11-02): ver
        # el comentario del test anterior.
        terminado = session.message_ids.filtered(
            lambda m: 'Terminado' in (m.body or '')
        ).sorted('id', reverse=True)[0]
        self.assertIn(f'terminado por {self.operator_a.name}', terminado.body)
        self.assertNotIn('inició', terminado.body)
        self.assertEqual(
            terminado.body.count(self.operator_a.name), 2,
            'El nombre aparece una vez en "terminado por" y otra en el '
            'reparto — nunca dos veces en una cláusula de inicio/fin',
        )

    def test_terminado_chatter_does_not_duplicate_on_repeated_call(self):
        session = self._create_session()
        line = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_assign()
        self._weigh_as(line, self.operator_a, 2.0)

        terminado_count = len(session.message_ids.filtered(
            lambda m: 'Terminado' in (m.body or '')
        ))
        self.assertEqual(terminado_count, 1)
        messages_before = len(session.message_ids)
        # Simula una ruta repetida/reconexión que vuelve a llamar el
        # hook — el claim ya quedó sin dueño, no debe volver a postear.
        line._maybe_release_finished_claim()
        self.assertEqual(len(session.message_ids), messages_before)

    def test_terminado_chatter_shows_both_operators_after_stop_and_resume(self):
        session = self._create_session()
        line1 = self._create_line(session, needs_weighing=True, estimated_kg=2.0)
        line2 = self._create_line(session, needs_weighing=True, estimated_kg=3.0)
        claim = session.product_claim_ids
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_assign()
        self._weigh_as(line1, self.operator_a, 2.0)
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_a)):
            claim.action_stop('sin_stock')
        with patch(REQUEST_PATCH_TARGET_CLAIM, self._request_as(self.operator_b)):
            claim.action_resume()
        self._weigh_as(line2, self.operator_b, 3.0)

        # filtered, no el último mensaje a secas (E5, 2026-11-02): ver
        # el comentario de test_terminado_chatter_shows_breakdown_and_
        # different_start_end.
        terminado = session.message_ids.filtered(
            lambda m: 'Terminado' in (m.body or '')
        ).sorted('id', reverse=True)[0]
        self.assertIn('Terminado', terminado.body)
        self.assertIn(self.operator_a.name, terminado.body)
        self.assertIn(self.operator_b.name, terminado.body)
        self.assertIn(f'terminó {self.operator_b.name}', terminado.body)
