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
        self.assertTrue(
            line.is_qty_estimated,
            'action_mark_line_ready() acepta lo pedido sin verificar, '
            'por definición — debe marcarlo (Tech Lead, punto b.3)',
        )

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
        directo, sin pesaje) — mismo bloqueo por ownership que el camino
        de pesaje real: tras la primera, el claim se libera y la segunda
        se bloquea con UserError antes de tocar nada."""
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
            with self.assertRaises(UserError):
                line.with_context(
                    guapante_picking_flow=True, guapante_qty_estimated=True,
                ).write({'actual_kg': 4.0})
        self.assertEqual(Summary.total_done_kg, kg_after_first)
        self.assertTrue(line.is_qty_estimated)
        self.assertEqual(line.actual_kg, 4.0)

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

    def test_action_save_line_weight_double_call_registers_once(self):
        """Peso Nivel 2 (Tech Lead, 2026-10-29): aunque un doble Enter o
        doble clic en el cliente llegue a disparar dos RPC al servidor
        en secuencia, el guardado queda registrado una sola vez. Al
        terminar la primera llamada, esta línea era la última pendiente
        de su plantilla — el claim se libera (Fase B) — así que la
        segunda llamada ya no pasa el chequeo de ownership y se
        bloquea con UserError antes de volver a tocar nada; no es un
        no-op silencioso, es un bloqueo explícito."""
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
            with self.assertRaises(UserError):
                session.with_context(
                    guapante_picking_flow=True,
                ).action_save_line_weight(line.id)
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
        pega al write() real). PreparationDayLine.write() exige
        ownership ANTES de escribir nada — con el claim ya liberado tras
        la primera llamada, la segunda se bloquea con UserError sin
        tocar el log ni total_done_kg."""
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
            with self.assertRaises(UserError):
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
