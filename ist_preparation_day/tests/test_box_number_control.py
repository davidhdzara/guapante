# -*- coding: utf-8 -*-
"""Control de numeración de cajas (lote 4): candado, historial inalterable,
duplicados, revisión automática y reinicio con motivo."""
from odoo import SUPERUSER_ID, api, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ist_preparation_day.models.box_number import (
    CTX_ORIGIN,
    ORIGIN_ALTA,
    box_origin,
)
from odoo.addons.ist_preparation_day.models.preparation_day import (
    _date_to_utc_range,
)

from .box_helpers import set_box


@tagged('post_install', '-at_install')
class TestBoxNumberControl(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        wh = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        wh.delivery_steps = 'pick_ship'
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente cajas'})
        cls.product = cls.env['product.product'].create({
            'name': 'Producto cajas', 'type': 'consu', 'list_price': 10.0,
        })
        cls.day = fields.Date.add(
            fields.Date.context_today(cls.env['sale.order']), days=40)
        cls.Log = cls.env['guapante.box.number.log']

    def _order(self, day=None):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1})],
        })
        order.action_confirm()
        dt_start, _e = _date_to_utc_range(self.env, day or self.day)
        for p in order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
            p.scheduled_date = dt_start
        return order

    def _assign(self, day=None):
        self.env['sale.order']._assign_daily_sequences(day or self.day)

    # ── candado ──

    def test_manual_write_is_rejected_even_for_superuser(self):
        order = self._order()
        self._assign()
        self.assertEqual(order.daily_sequence, 1)
        for env in (self.env, api.Environment(self.env.cr, SUPERUSER_ID, {})):
            with self.assertRaises(UserError):
                with self.cr.savepoint():
                    env['sale.order'].browse(order.id).write(
                        {'daily_sequence': 9})
            with self.assertRaises(UserError):
                with self.cr.savepoint():
                    env['sale.order'].browse(order.id).write(
                        {'daily_sequence': 0})
        order.invalidate_recordset()
        self.assertEqual(order.daily_sequence, 1)

    def test_plain_string_context_cannot_forge_the_lock(self):
        """El contexto de un cliente JSON-RPC solo trae str planos."""
        order = self._order()
        self._assign()
        with self.assertRaises(UserError):
            order.sudo().with_context(
                guapante_box_origin='reset',
                guapante_box_reason='forjado',
            ).write({'daily_sequence': 0})

    def test_create_with_number_is_rejected(self):
        with self.assertRaises(UserError):
            self.env['sale.order'].create({
                'partner_id': self.partner.id, 'daily_sequence': 4})

    def test_renumber_positive_to_positive_is_rejected_even_with_origin(self):
        order = self._order()
        self._assign()
        with self.assertRaises(UserError):
            order.with_context(
                **{CTX_ORIGIN: box_origin(ORIGIN_ALTA)}
            ).write({'daily_sequence': 7})

    def test_write_same_value_is_allowed(self):
        order = self._order()
        self._assign()
        order.write({'daily_sequence': order.daily_sequence})

    # ── historial ──

    def test_assign_is_logged_with_origin_alta(self):
        order = self._order()
        self._assign()
        log = self.Log.search([('order_id', '=', order.id)])
        self.assertEqual(len(log), 1)
        self.assertEqual(
            (log.old_sequence, log.new_sequence, log.origin, log.box_date),
            (0, 1, 'alta', self.day))
        self.assertEqual(log.order_name, order.name)

    def test_log_is_immutable_even_as_superuser(self):
        order = self._order()
        self._assign()
        log = self.Log.search([('order_id', '=', order.id)])
        for rec in (log, log.sudo(), log.with_user(SUPERUSER_ID)):
            with self.assertRaises(UserError):
                rec.write({'new_sequence': 99})
            with self.assertRaises(UserError):
                rec.unlink()

    def test_log_acl_is_read_only(self):
        acls = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'guapante.box.number.log')])
        self.assertTrue(acls)
        for acl in acls:
            self.assertFalse(acl.perm_write or acl.perm_create or acl.perm_unlink)

    def test_relocation_is_logged(self):
        order = self._order()
        self._assign()
        other = fields.Date.add(self.day, days=1)
        dt_start, _e = _date_to_utc_range(self.env, other)
        order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal'
            and p.state not in ('done', 'cancel')
        ).write({'scheduled_date': dt_start})
        origins = self.Log.search(
            [('order_id', '=', order.id)], order='id').mapped('origin')
        self.assertEqual(origins[0], 'alta')
        self.assertIn('reubicacion', origins)

    # ── duplicados ──

    def test_duplicate_box_same_day_is_rejected(self):
        o1 = self._order()
        o2 = self._order()
        self._assign()
        self.assertEqual((o1.daily_sequence, o2.daily_sequence), (1, 2))
        set_box(o2, 0)
        with self.assertRaises(ValidationError):
            o2.with_context(
                **{CTX_ORIGIN: box_origin(ORIGIN_ALTA)}
            ).write({'daily_sequence': 1})

    def test_cancellation_gap_is_not_an_error(self):
        o1 = self._order()
        o2 = self._order()
        o3 = self._order()
        self._assign()
        o2.sudo()._action_cancel()
        findings = self.env['sale.order']._guapante_check_box_numbering(self.day)
        self.assertFalse([f for f in findings if f[0] == 'duplicate'])
        self.assertEqual([o1.daily_sequence, o3.daily_sequence], [1, 3])

    # ── revisión automática ──

    def test_review_detects_seeded_duplicate_and_is_idempotent(self):
        o1 = self._order()
        o2 = self._order()
        self._assign()
        # siembra de un duplicado fuera del ORM (como un dato histórico)
        self.env.cr.execute(
            'UPDATE sale_order SET daily_sequence = 1 WHERE id = %s', (o2.id,))
        o2.invalidate_recordset(['daily_sequence'])
        SO = self.env['sale.order']
        findings = SO._guapante_check_box_numbering(self.day)
        dup = [f for f in findings if f[0] == 'duplicate']
        self.assertEqual({f[1] for f in dup}, {o1, o2})
        Issue = self.env['guapante.box.number.issue']
        n = Issue.search_count([('kind', '=', 'duplicate'), ('state', '=', 'open')])
        SO._guapante_check_box_numbering(self.day)
        self.assertEqual(
            Issue.search_count([('kind', '=', 'duplicate'), ('state', '=', 'open')]),
            n, 'segunda pasada no duplica registros')
        # al corregir, la inconsistencia se cierra sola
        self.env.cr.execute(
            'UPDATE sale_order SET daily_sequence = 2 WHERE id = %s', (o2.id,))
        o2.invalidate_recordset(['daily_sequence'])
        SO._guapante_check_box_numbering(self.day)
        self.assertFalse(Issue.search([
            ('kind', '=', 'duplicate'), ('state', '=', 'open'),
            ('box_date', '=', self.day)]))

    def test_review_detects_change_outside_the_log(self):
        o1 = self._order()
        self._assign()
        session = self.env['guapante.preparation.day'].create({'date': self.day})
        session.action_load()
        self.env.cr.execute(
            'UPDATE sale_order SET daily_sequence = 44 WHERE id = %s', (o1.id,))
        o1.invalidate_recordset(['daily_sequence'])
        findings = self.env['sale.order']._guapante_check_box_numbering(self.day)
        self.assertIn('outside_log', [f[0] for f in findings])

    def test_cron_runs_without_error(self):
        self.env['sale.order']._cron_check_box_numbering()

    # ── reinicio con motivo, solo admin ──

    def _reset_wizard(self, user, pickings, reason):
        wiz = self.env['guapante.box.reset.wizard'].with_user(user).create({
            'picking_ids': [(6, 0, pickings.ids)], 'reason': reason})
        return wiz

    def test_reset_requires_reason_and_is_logged(self):
        order = self._order()
        self._assign()
        pickings = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal')
        with self.assertRaises(UserError):
            pickings._guapante_reset_boxes('   ')
        order.invalidate_recordset()
        self.assertEqual(order.daily_sequence, 1)
        pickings._guapante_reset_boxes('Prueba de reinicio')
        order.invalidate_recordset()
        self.assertEqual(order.daily_sequence, 0)
        log = self.Log.search(
            [('order_id', '=', order.id), ('origin', '=', 'reset')])
        self.assertEqual(log.reason, 'Prueba de reinicio')
        self.assertEqual((log.old_sequence, log.new_sequence), (1, 0))

    def test_reset_only_for_admin(self):
        order = self._order()
        self._assign()
        pickings = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal')
        plain = self.env['res.users'].create({
            'name': 'Interno', 'login': 'interno_cajas',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            pickings.with_user(plain).action_reset_daily_sequence()
        action = pickings.with_user(SUPERUSER_ID).action_reset_daily_sequence()
        self.assertEqual(action['res_model'], 'guapante.box.reset.wizard')
        self.assertTrue(action['views'])

    def test_wizard_confirm_resets_with_reason(self):
        order = self._order()
        self._assign()
        pickings = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal')
        wiz = self._reset_wizard(self.env.user, pickings, 'Corrección del día')
        # el usuario de pruebas del framework es admin de base
        wiz.action_confirm()
        order.invalidate_recordset()
        self.assertEqual(order.daily_sequence, 0)
