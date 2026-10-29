# -*- coding: utf-8 -*-
"""Condición 3 (Tech Lead, 2026-10-29): al reubicar una línea entre
jornadas, el claim del Nivel 1 de Picking tiene que seguirla — vive en
este módulo (no en ist_preparation_day), así que necesita su propio
gancho (_guapante_after_relocate)."""
from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.models.preparation_day import (
    _date_to_utc_range,
)
from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)


@tagged('post_install', '-at_install')
class TestPreparationDayRelocationClaims(TestPreparationDay):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.day_a = fields.Date.add(cls.delivery_date, days=50)
        cls.day_b = fields.Date.add(cls.day_a, days=3)
        cls.product_weight_2 = cls.env['product.product'].create({
            'name': 'Producto Pesable Reloc 2',
            'type': 'consu',
            'list_price': 1000.0,
            'uom_id': cls.env.ref('uom.product_uom_kgm').id,
            'uom_po_id': cls.env.ref('uom.product_uom_kgm').id,
        })

    def _confirmed_order_on(self, day):
        order = self.env['sale.order'].create({
            'partner_id': self.child_partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product_weight.id,
                'product_uom_qty': 2.0,
            })],
        })
        order.action_confirm()
        dt_start, _dt_end = _date_to_utc_range(self.env, day)
        pick = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal'
            and p.state not in ('done', 'cancel')
        )
        pick.scheduled_date = dt_start
        return order, pick

    def _confirmed_multiline_order_on(self, day):
        order = self.env['sale.order'].create({
            'partner_id': self.child_partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product_weight.id,
                    'product_uom_qty': 2.0,
                }),
                (0, 0, {
                    'product_id': self.product_weight_2.id,
                    'product_uom_qty': 1.0,
                }),
            ],
        })
        order.action_confirm()
        dt_start, _dt_end = _date_to_utc_range(self.env, day)
        pick = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'internal'
            and p.state not in ('done', 'cancel')
        )
        pick.scheduled_date = dt_start
        return order, pick

    def _session_on(self, day):
        Session = self.env['guapante.preparation.day'].sudo().search(
            [('date', '=', day)], limit=1,
        )
        if not Session:
            Session = self.env['guapante.preparation.day'].create(
                {'date': day},
            )
        Session.action_load()
        return Session

    def test_multiline_order_moves_both_claims_to_new_session(self):
        """DEF-01 (Tech Lead, 2026-10-29): un pedido con 2 líneas de 2
        productos distintos no debe reventar al reubicar, y los claims
        de AMBOS productos deben seguir a la línea."""
        order, pick = self._confirmed_multiline_order_on(self.day_a)
        session_a = self._session_on(self.day_a)
        claim_a_1 = session_a.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        claim_a_2 = session_a.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight_2.product_tmpl_id
        )
        self.assertTrue(claim_a_1 and claim_a_2)

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.write({'scheduled_date': dt_start_b})  # no debe lanzar ValueError

        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        claim_b_1 = session_b.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        claim_b_2 = session_b.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight_2.product_tmpl_id
        )
        self.assertTrue(claim_b_1, 'El claim del primer producto debe seguir a la nueva jornada')
        self.assertTrue(claim_b_2, 'El claim del segundo producto debe seguir a la nueva jornada')

        session_a.invalidate_recordset()
        self.assertFalse(
            session_a.product_claim_ids.filtered(
                lambda c: c.product_tmpl_id in (
                    self.product_weight.product_tmpl_id,
                    self.product_weight_2.product_tmpl_id,
                )
            ),
            'Sin líneas de ninguno de los dos productos, los claims viejos deben limpiarse',
        )

    def test_relocation_moves_claim_to_new_session_not_old(self):
        order, pick = self._confirmed_order_on(self.day_a)
        session_a = self._session_on(self.day_a)
        claim_a = session_a.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        self.assertTrue(claim_a, 'Debe nacer el claim al cargar la jornada A')

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick.write({'scheduled_date': dt_start_b})

        session_b = self.env['guapante.preparation.day'].search(
            [('date', '=', self.day_b)], limit=1,
        )
        claim_b = session_b.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        self.assertTrue(
            claim_b, 'El claim tiene que existir en la jornada nueva',
        )

        session_a.invalidate_recordset()
        claim_a_still = session_a.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        self.assertFalse(
            claim_a_still,
            'Sin más líneas de ese producto, el claim viejo debe limpiarse',
        )

    def test_relocation_does_not_duplicate_or_overwrite_existing_claim(self):
        # Dos órdenes distintas, mismo producto: una ya cargada en B
        # (con su claim, asignado a un operario), otra que se mueve de
        # A a B después — no debe duplicar el claim ni tocar el dueño.
        order_existing, _pick_existing = self._confirmed_order_on(self.day_b)
        session_b = self._session_on(self.day_b)
        claim_b_before = session_b.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        self.assertEqual(len(claim_b_before), 1)
        operator = self.env['hr.employee'].create({
            'name': 'Operario Reloc Claims',
            'l10n_co_ne_payment_method': '10',
        })
        claim_b_before.sudo().write({
            'assigned_employee_id': operator.id,
            'assigned_date': fields.Datetime.now(),
        })

        order_moving, pick_moving = self._confirmed_order_on(self.day_a)
        self._session_on(self.day_a)

        dt_start_b, _ = _date_to_utc_range(self.env, self.day_b)
        pick_moving.write({'scheduled_date': dt_start_b})

        session_b.invalidate_recordset()
        claims_b_after = session_b.product_claim_ids.filtered(
            lambda c: c.product_tmpl_id == self.product_weight.product_tmpl_id
        )
        self.assertEqual(
            len(claims_b_after), 1,
            'No debe duplicarse el claim que ya existía en B',
        )
        self.assertEqual(
            claims_b_after.assigned_employee_id, operator,
            'No debe pisarse el dueño del claim que ya existía en B',
        )
