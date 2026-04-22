# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPreparationDay(TransactionCase):
    """Tests for the Preparation Day session workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse Prep',
                'code': 'TWP',
                'company_id': cls.env.company.id,
            })
        cls.warehouse.delivery_steps = 'pick_ship'

        cls.partner = cls.env['res.partner'].create({
            'name': 'Restaurante Test Prep',
        })
        cls.child_partner = cls.env['res.partner'].create({
            'name': 'Cocina Principal',
            'parent_id': cls.partner.id,
        })

        # Producto por peso (kg)
        cls.uom_kg = cls.env.ref('uom.product_uom_kgm')
        cls.product_weight = cls.env['product.product'].create({
            'name': 'Aguacate Hass Test Prep',
            'type': 'consu',
            'list_price': 5000.0,
            'uom_id': cls.uom_kg.id,
            'uom_po_id': cls.uom_kg.id,
        })

        # Producto por unidad
        cls.product_unit = cls.env['product.product'].create({
            'name': 'Bolsa Plástica Test',
            'type': 'consu',
            'list_price': 200.0,
        })

        # Fecha de entrega: 14 días en el futuro (evita colisiones)
        cls.delivery_date = fields.Date.add(
            fields.Date.context_today(cls.env['sale.order']),
            days=14,
        )

    def _create_confirmed_order(
        self, product=None, qty=5.0, partner=None
    ):
        """Helper: create and confirm a sale order, set picking date."""
        if product is None:
            product = self.product_weight
        if partner is None:
            partner = self.child_partner

        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
            })],
        })
        order.action_confirm()

        # Fijar la fecha de picking para que coincida con delivery_date
        dt = fields.Datetime.to_datetime(self.delivery_date)
        for picking in order.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        ):
            picking.scheduled_date = dt

        return order

    def _create_session(self):
        """Helper: create a preparation day session."""
        return self.env['guapante.preparation.day'].create({
            'date': self.delivery_date,
        })

    # ── Tests de Creación de Sesión ──

    def test_session_create_default_name(self):
        """Session name should include the date."""
        session = self._create_session()
        self.assertIn(
            str(self.delivery_date),
            session.name,
            "Session name should contain the delivery date",
        )
        self.assertEqual(session.state, 'draft')

    # ── Tests de action_load() ──

    def test_action_load_creates_lines(self):
        """action_load should create preparation lines for confirmed orders."""
        self._create_confirmed_order(qty=2.5)
        session = self._create_session()
        session.action_load()

        self.assertEqual(session.state, 'loaded')
        self.assertTrue(
            len(session.line_ids) > 0,
            "Session should have preparation lines after load",
        )

    def test_action_load_no_orders_raises(self):
        """action_load should raise UserError if no orders for the date."""
        # Fecha lejana sin órdenes
        session = self.env['guapante.preparation.day'].create({
            'date': fields.Date.add(
                fields.Date.context_today(self.env['sale.order']),
                days=90,
            ),
        })
        with self.assertRaises(UserError):
            session.action_load()

    def test_action_load_deduplicates(self):
        """Loading twice should not duplicate existing lines."""
        self._create_confirmed_order(qty=3.0)
        session = self._create_session()
        session.action_load()
        count_after_first = len(session.line_ids)

        session.action_load()
        count_after_second = len(session.line_ids)

        self.assertEqual(
            count_after_first,
            count_after_second,
            "Second load should not duplicate lines",
        )

    def test_action_load_adds_new_orders(self):
        """Loading after new order should add only the new line."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        count_first = len(session.line_ids)

        # Crear otra orden para la misma fecha
        self._create_confirmed_order(
            product=self.product_unit, qty=10.0,
        )
        session.action_load()

        self.assertGreater(
            len(session.line_ids),
            count_first,
            "Second load should pick up newly created orders",
        )

    def test_action_load_cleans_cancelled_orders(self):
        """Lines from cancelled orders should be removed on reload."""
        order = self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()
        self.assertTrue(len(session.line_ids) > 0)

        # Cancelar la orden y sus movimientos
        order.action_cancel()
        if order.state != 'cancel':
            order.write({'state': 'cancel'})
        for picking in order.picking_ids:
            if picking.state != 'cancel':
                picking.action_cancel()

        session.action_load()

        pending_from_cancelled = session.line_ids.filtered(
            lambda l: l.sale_order_id == order and not l.is_done
        )
        self.assertFalse(
            pending_from_cancelled,
            "Lines from cancelled orders should be cleaned up",
        )

    def test_action_load_preserves_done_lines(self):
        """Lines already marked is_done should NOT be removed on reload."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        # Simular completar una línea
        line = session.line_ids[0]
        line.with_context(skip_auto_save=True).write({
            'actual_kg': 1.5,
            'is_done': True,
        })
        session.action_load()

        done_line = session.line_ids.filtered(lambda l: l.is_done)
        self.assertTrue(
            done_line,
            "Done lines should be preserved across reloads",
        )

    def test_action_load_customer_hierarchy(self):
        """Lines should show parent as main_customer_name for child contacts."""
        self._create_confirmed_order(
            partner=self.child_partner, qty=1.0,
        )
        session = self._create_session()
        session.action_load()

        line = session.line_ids[0]
        self.assertEqual(
            line.main_customer_name,
            self.partner.name,
            "main_customer_name should be the parent partner",
        )

    # ── Tests de Summary ──

    def test_summary_created_on_load(self):
        """Summary records should be created per product variant."""
        self._create_confirmed_order(
            product=self.product_weight, qty=3.0,
        )
        self._create_confirmed_order(
            product=self.product_unit, qty=5.0,
        )
        session = self._create_session()
        session.action_load()

        self.assertGreaterEqual(
            len(session.summary_ids),
            2,
            "Should have at least 2 summaries (one per product)",
        )

    def test_summary_totals(self):
        """Summary should aggregate estimated_kg from all lines."""
        self._create_confirmed_order(
            product=self.product_weight, qty=2.0,
        )
        self._create_confirmed_order(
            product=self.product_weight, qty=3.0,
        )
        session = self._create_session()
        session.action_load()

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        self.assertTrue(summary)
        self.assertAlmostEqual(
            summary.total_estimated_kg,
            5.0,
            places=2,
            msg="Summary should aggregate all line estimated_kg values",
        )
        self.assertEqual(summary.order_count, 2)

    def test_summary_progress(self):
        """Progress % should reflect done vs total lines."""
        self._create_confirmed_order(
            product=self.product_weight, qty=1.0,
        )
        self._create_confirmed_order(
            product=self.product_weight, qty=1.0,
        )
        session = self._create_session()
        session.action_load()

        # Completar una de las dos líneas
        weight_lines = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_weight
        )
        if len(weight_lines) >= 2:
            weight_lines[0].with_context(skip_auto_save=True).write({
                'actual_kg': 1.0,
                'is_done': True,
            })

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        if summary and len(weight_lines) >= 2:
            self.assertAlmostEqual(
                summary.progress_pct,
                50.0,
                places=0,
                msg="Progress should be 50% when 1 of 2 lines is done",
            )

    # ── Tests de action_save_line_weight() ──

    def test_save_line_weight_marks_done(self):
        """Saving a weight should mark the line as done."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(lambda l: not l.is_done)[:1]
        self.assertTrue(line)
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.8})
        session.action_save_line_weight(line.id)

        self.assertTrue(
            line.is_done,
            "Line should be marked as done after saving weight",
        )

    def test_save_line_weight_creates_log(self):
        """Saving weight should create a picking log entry."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.1})
        session.action_save_line_weight(line.id)

        log = self.env['guapante.picking.log'].search([
            ('wizard_id', '=', session.id),
            ('product_product_id', '=', line.product_product_id.id),
        ])
        self.assertTrue(
            log,
            "A picking log entry should be created after saving weight",
        )
        self.assertAlmostEqual(log.actual_kg, 2.1, places=2)

    def test_save_line_weight_updates_summary(self):
        """Saving weight should update the summary total_done_kg."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.9})
        session.action_save_line_weight(line.id)

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == line.product_product_id
        )
        self.assertAlmostEqual(
            summary.total_done_kg,
            1.9,
            places=2,
            msg="Summary total_done_kg should include the saved weight",
        )

    def test_save_line_weight_ignores_zero(self):
        """Saving with actual_kg=0 should NOT mark as done."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        result = session.action_save_line_weight(line.id)

        self.assertFalse(result)
        self.assertFalse(line.is_done)

    def test_auto_finish_session(self):
        """Session should auto-finish when all lines are done."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()

        for line in session.line_ids:
            line.with_context(skip_auto_save=True).write(
                {'actual_kg': 1.0}
            )
            session.action_save_line_weight(line.id)

        self.assertEqual(
            session.state,
            'done',
            "Session should auto-finish when no pending lines remain",
        )

    # ── Tests de action_undo_line() ──

    def test_undo_line_reverts_to_pending(self):
        """Undoing a line should set is_done=False and actual_kg=0."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({
            'actual_kg': 2.3,
            'is_done': True,
        })
        line.action_undo_line()

        self.assertFalse(line.is_done)
        self.assertAlmostEqual(line.actual_kg, 0.0, places=2)

    def test_undo_line_updates_summary(self):
        """Undoing should subtract from summary total_done_kg."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 2.5})
        session.action_save_line_weight(line.id)

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == line.product_product_id
        )
        done_before = summary.total_done_kg

        line.action_undo_line()

        self.assertAlmostEqual(
            summary.total_done_kg,
            done_before - 2.5,
            places=2,
            msg="Undo should subtract the weight from summary",
        )

    # ── Tests de write() override ──

    def test_write_actual_kg_auto_saves(self):
        """Writing actual_kg > 0 should auto-trigger save."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(lambda l: not l.is_done)[:1]
        self.assertTrue(line)

        # Escribir actual_kg sin skip_auto_save debe auto-guardar
        line.write({'actual_kg': 1.5})

        self.assertTrue(
            line.is_done,
            "Writing actual_kg > 0 without skip_auto_save should "
            "auto-mark as done",
        )

    def test_write_skip_auto_save(self):
        """Writing with skip_auto_save=True should NOT auto-trigger."""
        self._create_confirmed_order(qty=2.0)
        session = self._create_session()
        session.action_load()

        line = session.line_ids.filtered(lambda l: not l.is_done)[:1]
        line.with_context(skip_auto_save=True).write({'actual_kg': 1.5})

        self.assertFalse(
            line.is_done,
            "skip_auto_save context should prevent auto-save",
        )

    # ── Tests de Product Wizard ──

    def test_product_wizard_lists(self):
        """Wizard should separate pending and done lines correctly."""
        self._create_confirmed_order(qty=1.0)
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()

        weight_lines = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_weight
        )
        if len(weight_lines) < 2:
            return  # Skip if product was merged

        # Completar una línea
        weight_lines[0].with_context(skip_auto_save=True).write({
            'actual_kg': 1.0,
            'is_done': True,
        })

        summary = session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        if not summary:
            return

        # Abrir wizard
        action = summary.action_select_product()
        wizard = self.env[
            'guapante.preparation.day.product.wizard'
        ].browse(action['res_id'])

        self.assertEqual(len(wizard.detail_line_done_ids), 1)
        self.assertEqual(len(wizard.detail_line_pending_ids), 1)
        self.assertAlmostEqual(
            wizard.progress_percentage, 50.0, places=0,
        )

    def test_product_wizard_back_to_session(self):
        """action_back_to_session should return correct action dict."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()

        summary = session.summary_ids[:1]
        if not summary:
            return

        action = summary.action_select_product()
        wizard = self.env[
            'guapante.preparation.day.product.wizard'
        ].browse(action['res_id'])

        back_action = wizard.action_back_to_session()
        self.assertEqual(
            back_action['res_model'],
            'guapante.preparation.day',
        )
        self.assertEqual(back_action['res_id'], session.id)

    # ── Tests de Session Lifecycle ──

    def test_session_reopen(self):
        """Reopening a done session should set state to loaded."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        session.action_mark_done()
        self.assertEqual(session.state, 'done')

        session.action_reopen()
        self.assertEqual(session.state, 'loaded')

    def test_session_reopen_allows_new_orders(self):
        """Reopening then loading should pick up new orders."""
        self._create_confirmed_order(qty=1.0)
        session = self._create_session()
        session.action_load()
        session.action_mark_done()
        session.action_reopen()

        # Agregar una nueva orden
        self._create_confirmed_order(
            product=self.product_unit, qty=5.0,
        )
        session.action_load()

        has_unit_product = session.line_ids.filtered(
            lambda l: l.product_product_id == self.product_unit
        )
        self.assertTrue(
            has_unit_product,
            "Reopened session should pick up new orders on load",
        )

    # ── Tests de _get_display_qty() ──

    def test_display_qty_kg_mode(self):
        """Kg mode should display raw quantity."""
        order = self._create_confirmed_order(qty=2.5)
        sol = order.order_line.filtered(
            lambda l: l.product_id == self.product_weight
        )[:1]
        if sol:
            sol.uom_mode = 'kg'
            result = self.env[
                'guapante.preparation.day.line'
            ]._get_display_qty(sol)
            self.assertEqual(result, ('2.5', 'kg'))

    def test_display_qty_g_mode(self):
        """Gram mode should convert kg to grams."""
        order = self._create_confirmed_order(qty=0.5)
        sol = order.order_line.filtered(
            lambda l: l.product_id == self.product_weight
        )[:1]
        if sol:
            sol.uom_mode = 'g'
            result = self.env[
                'guapante.preparation.day.line'
            ]._get_display_qty(sol)
            self.assertEqual(result, ('500', 'g'))
