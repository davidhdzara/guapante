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

REQUEST_PATCH_TARGET_SCRAP = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_scrap.request'
)
REQUEST_PATCH_TARGET_LINE = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_line.request'
)
REQUEST_PATCH_TARGET_CLAIM = (
    'odoo.addons.ist_preparation_day_picking.models'
    '.preparation_day_product_claim.request'
)


@tagged('post_install', '-at_install')
class TestPreparationDayPickingFaseD(TestPreparationDay):
    """Fase D: desechos nativos (stock.scrap) y notas del Nivel 2.

    Mismos helpers que los tests de Fase B/C (_request_as, grupo de
    Picking en el usuario de test) — no se duplican, se reconstruyen
    acá porque cada archivo de test hereda TestPreparationDay por su
    cuenta (mismo patrón ya usado en test_preparation_day_picking_fase_c.py).
    """

    def setUp(self):
        super().setUp()
        self.Claim = self.env['guapante.preparation.day.product.claim']
        self.Line = self.env['guapante.preparation.day.line']
        self.env.user.sudo().write({
            'groups_id': [(4, self.env.ref(
                'ist_preparation_day_picking.group_preparation_picking_operator'
            ).id)],
        })
        self.operator_a = self.env['hr.employee'].create({
            'name': 'Operario Fase D A',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })
        self.operator_b = self.env['hr.employee'].create({
            'name': 'Operario Fase D B',
            'is_guapante_prep_operator': True,
            'l10n_co_ne_payment_method': '10',
        })

    def _request_as(self, employee):
        mock_request = MagicMock()
        mock_request.session = {}
        set_active_prep_operator(mock_request.session, employee.id)
        return mock_request

    def _load_session_with_product(self, qty=2.0, product=None):
        self._create_confirmed_order(qty=qty, product=product)
        session = self._create_session()
        session.action_load()
        return session

    def _assign_to_operator_a(self, claim):
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_CLAIM, mock_a):
            claim.action_assign()

    def _create_session_on(self, days_offset):
        """_create_session() del padre siempre usa self.delivery_date —
        hay una sola sesión por fecha (constraint real) — una segunda
        sesión real necesita otra fecha. Mismo helper que
        test_preparation_day_picking_fase_c.py."""
        date = fields.Date.add(self.delivery_date, days=days_offset)
        return self.env['guapante.preparation.day'].create({'date': date})

    # ── stock.scrap — Fase D, Desechar ──

    def test_scrap_requires_active_operator(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        no_operator = MagicMock()
        no_operator.session = {}
        Scrap = self.env['stock.scrap'].with_context(
            guapante_picking_flow=True,
            picking_wizard_id=session.id,
            picking_claim_id=claim.id,
        ).create({'product_id': self.product_weight.id, 'scrap_qty': 1.0})
        with patch(REQUEST_PATCH_TARGET_SCRAP, no_operator):
            with self.assertRaises(UserError):
                Scrap.do_scrap()

    def test_scrap_requires_claim_and_wizard_in_context(self):
        """Tech Lead, corrección 2: con guapante_picking_flow pero sin
        picking_claim_id/picking_wizard_id, nunca cae al flujo sin
        chequeo — se corta con UserError."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        Scrap = self.env['stock.scrap'].with_context(
            guapante_picking_flow=True,
        ).create({'product_id': self.product_weight.id, 'scrap_qty': 1.0})
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_SCRAP, mock_a):
            with self.assertRaises(UserError):
                Scrap.do_scrap()

    def test_scrap_blocks_non_owner(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        Scrap = self.env['stock.scrap'].with_context(
            guapante_picking_flow=True,
            picking_wizard_id=session.id,
            picking_claim_id=claim.id,
        ).create({'product_id': self.product_weight.id, 'scrap_qty': 1.0})
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET_SCRAP, mock_b):
            with self.assertRaises(UserError):
                Scrap.do_scrap()

    def test_scrap_blocks_product_outside_claim_template(self):
        """Tech Lead, corrección 3: product_ids en el contexto del
        diálogo solo acota el domain del campo — no impide teclear otro
        producto por RPC directo. Server-side real en do_scrap()."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        other_product = self.env['product.product'].create({
            'name': 'Otro producto (fuera del claim)',
            'type': 'consu',
            'is_storable': True,
        })
        Scrap = self.env['stock.scrap'].with_context(
            guapante_picking_flow=True,
            picking_wizard_id=session.id,
            picking_claim_id=claim.id,
        ).create({'product_id': other_product.id, 'scrap_qty': 1.0})
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_SCRAP, mock_a):
            with self.assertRaises(UserError):
                Scrap.do_scrap()

    def test_scrap_blocks_claim_from_different_session(self):
        """Tech Lead (segunda revisión): wizard_id y claim_id vienen
        sueltos del contexto del cliente — ambos podrían existir pero
        apuntar a sesiones distintas (ej. una pestaña con contexto
        viejo tras F5 a medias). El claim tiene que ser de ESA sesión."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        other_session = self._create_session_on(days_offset=-10)
        Scrap = self.env['stock.scrap'].with_context(
            guapante_picking_flow=True,
            picking_wizard_id=other_session.id,
            picking_claim_id=claim.id,
        ).create({'product_id': self.product_weight.id, 'scrap_qty': 1.0})
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_SCRAP, mock_a):
            with self.assertRaises(UserError):
                Scrap.do_scrap()

    def test_scrap_sets_origin_from_session_when_missing(self):
        """Tech Lead, corrección 1: default_origin no sirve (el campo no
        está en stock_scrap_form_view2) — se escribe en do_scrap()."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        Scrap = self.env['stock.scrap'].with_context(
            guapante_picking_flow=True,
            picking_wizard_id=session.id,
            picking_claim_id=claim.id,
        ).create({'product_id': self.product_weight.id, 'scrap_qty': 1.0})
        self.assertFalse(Scrap.origin)
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_SCRAP, mock_a):
            Scrap.do_scrap()
        self.assertEqual(Scrap.origin, session.name)

    def test_scrap_posts_chatter_on_scrap_and_session(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        tag = self.env['stock.scrap.reason.tag'].create({'name': 'Prueba QA'})
        Scrap = self.env['stock.scrap'].with_context(
            guapante_picking_flow=True,
            picking_wizard_id=session.id,
            picking_claim_id=claim.id,
        ).create({
            'product_id': self.product_weight.id,
            'scrap_qty': 1.0,
            'scrap_reason_tag_ids': [(6, 0, [tag.id])],
        })
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_SCRAP, mock_a):
            Scrap.do_scrap()
        scrap_messages = Scrap.message_ids.mapped('body')
        self.assertTrue(any('Operario Fase D A' in m for m in scrap_messages))
        self.assertTrue(any('Prueba QA' in m for m in scrap_messages))
        session_messages = session.message_ids.mapped('body')
        self.assertTrue(any('Operario Fase D A' in m for m in session_messages))

    def test_scrap_insufficient_qty_path_still_posts_chatter(self):
        """product_weight tiene is_storable=False (no seteado en el
        fixture base) — _should_check_available_qty() lo salta siempre,
        así que nunca dispara el asistente de cantidad insuficiente.
        Producto storable propio + cantidad absurda para forzar ese
        camino. Se simula el Confirmar de ese asistente tal cual lo hace
        stock.warn.insufficient.qty.scrap.action_done()
        (scrap_id.do_scrap() con clean_context) para probar que el mismo
        hook de atribución también deja el chatter por ese camino."""
        storable_product = self.env['product.product'].create({
            'name': 'Producto storable Fase D',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.uom_kg.id,
            'uom_po_id': self.uom_kg.id,
        })
        session = self._load_session_with_product(product=storable_product)
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        Scrap = self.env['stock.scrap'].with_context(
            guapante_picking_flow=True,
            picking_wizard_id=session.id,
            picking_claim_id=claim.id,
        ).create({'product_id': storable_product.id, 'scrap_qty': 999999999.0})
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_SCRAP, mock_a):
            result = Scrap.action_validate()
            self.assertIsInstance(result, dict)
            self.assertEqual(result.get('res_model'), 'stock.warn.insufficient.qty.scrap')
            Scrap.do_scrap()
        self.assertTrue(
            any('Operario Fase D A' in m for m in Scrap.message_ids.mapped('body'))
        )

    def test_scrap_outside_picking_flow_unaffected(self):
        """Sin guapante_picking_flow en contexto: do_scrap() se comporta
        exactamente como el core — sin exigir operario ni postear nada
        propio (regresión: Picking no puede romper el uso normal de
        Inventario › Desechar)."""
        session = self._load_session_with_product()
        Scrap = self.env['stock.scrap'].create({
            'product_id': self.product_weight.id, 'scrap_qty': 1.0,
        })
        Scrap.do_scrap()  # sin request parcheado, sin operario — no debe fallar
        self.assertEqual(Scrap.state, 'done')
        self.assertFalse(
            any('por ' in (m or '') for m in Scrap.message_ids.mapped('body'))
        )

    # ── Notas (Nivel 2) ──

    def test_note_template_ordered_by_sequence(self):
        """search([]) sin acotar por id choca con plantillas reales que
        ya existan en la base (ej. las que David deje configuradas en
        staging) — se acota a los dos registros que crea este test."""
        Template = self.env['guapante.preparation.day.note.template']
        second = Template.create({'name': 'Segunda', 'sequence': 20})
        first = Template.create({'name': 'Primera', 'sequence': 10})
        names = Template.search([('id', 'in', (first | second).ids)]).mapped('name')
        self.assertEqual(names, ['Primera', 'Segunda'])

    def test_action_add_note_requires_active_operator(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        line = session.line_ids[0]
        no_operator = MagicMock()
        no_operator.session = {}
        with patch(REQUEST_PATCH_TARGET_LINE, no_operator):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).action_add_note('Nota de prueba')

    def test_action_add_note_blocks_non_owner(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        line = session.line_ids[0]
        mock_b = self._request_as(self.operator_b)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_b):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).action_add_note('Nota de prueba')

    def test_action_add_note_rejects_empty_text(self):
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        line = session.line_ids[0]
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a):
            with self.assertRaises(UserError):
                line.with_context(guapante_picking_flow=True).action_add_note('   ')

    def test_action_add_note_posts_to_picking_when_present(self):
        """_load_session_with_product() pasa por una orden confirmada de
        verdad — las líneas quedan con stock_move_id.picking_id real."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        line = session.line_ids[0]
        self.assertTrue(line.stock_move_id.picking_id)
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a):
            line.with_context(guapante_picking_flow=True).action_add_note('Caja golpeada en el camino')
        picking_messages = line.stock_move_id.picking_id.message_ids.mapped('body')
        self.assertTrue(any('Caja golpeada en el camino' in m for m in picking_messages))
        self.assertTrue(any('Operario Fase D A' in m for m in picking_messages))

    def test_action_add_note_escapes_html(self):
        """Tech Lead: texto libre de un operario tratado como HTML
        crudo por message_post() — "<b>hola</b> & chao" se renderizaba
        con negrita activa y "\\n" se perdía. plaintext2html() debe
        dejar las etiquetas escapadas (texto plano) y el salto como
        <br/>."""
        session = self._load_session_with_product()
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        line = session.line_ids[0]
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a):
            line.with_context(guapante_picking_flow=True).action_add_note(
                '<b>hola</b> & chao\nlinea 2'
            )
        Message = line.stock_move_id.picking_id.message_ids.filtered(
            lambda m: 'hola' in (m.body or '')
        )
        self.assertTrue(Message)
        body = Message[0].body
        self.assertNotIn('<b>hola</b>', body)
        self.assertIn('&lt;b&gt;hola&lt;/b&gt;', body)
        self.assertIn('&amp; chao', body)
        self.assertIn('<br', body)

    def test_action_add_note_falls_back_to_session_when_no_picking(self):
        """Caso borde (Tech Lead): una línea sin stock_move_id (p.ej.
        creada a mano, sin picking asociado) cae a la sesión. El
        número de caja ahora es related a sale_order_id.daily_sequence
        (R5, 2026-10-29) — por eso se arma una orden real en vez de
        forzar el valor directo en la línea, que ya es readonly."""
        order = self._create_confirmed_order()
        order.daily_sequence = 7
        session = self._create_session()
        line = self.Line.create({
            'wizard_id': session.id,
            'product_id': self.product_weight.product_tmpl_id.id,
            'product_product_id': self.product_weight.id,
            'sale_order_id': order.id,
        })
        self.assertFalse(line.stock_move_id)
        self.assertEqual(line.daily_sequence, 7)
        claim = session.product_claim_ids
        self._assign_to_operator_a(claim)
        mock_a = self._request_as(self.operator_a)
        with patch(REQUEST_PATCH_TARGET_LINE, mock_a):
            line.with_context(guapante_picking_flow=True).action_add_note('Sin stock suficiente')
        session_messages = session.message_ids.mapped('body')
        self.assertTrue(any('Caja #7' in m and 'Sin stock suficiente' in m for m in session_messages))
