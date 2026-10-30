# -*- coding: utf-8 -*-
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)


@tagged('post_install', '-at_install')
class TestPreparationDayPickingFaseE1(TestPreparationDay):
    """Fase E1 del plan de carga automática (2026-10-29): refactor puro
    de action_load() — extrae _guapante_add_order_lines() sin cambio de
    comportamiento.

    Test de caracterización pedido por Tech Lead: fija con exactitud los
    valores de línea/summary/claim que produce action_load() HOY (antes
    del refactor), para correr exactamente igual después del refactor y
    probar que no cambió nada — mismas líneas, mismos summaries, mismos
    claims del Nivel 1 (que vive en este módulo hijo, no en el padre).
    """

    def test_action_load_characterization_lines_summaries_claims(self):
        order_a = self._create_confirmed_order(
            product=self.product_weight, qty=5.0, partner=self.child_partner,
        )
        # Mismo producto por peso, cliente SIN padre — ejercita la rama
        # main_cust_name = partner.name directo (no partner.parent_id.name)
        # y agrega con order_a en el summary de product_weight.
        order_b = self._create_confirmed_order(
            product=self.product_weight, qty=2.0, partner=self.partner,
        )
        order_c = self._create_confirmed_order(
            product=self.product_unit, qty=3.0, partner=self.child_partner,
        )
        # El create() de sale.order.line (theme_guapante) auto-asigna
        # uom_mode='kg' para un producto por peso si no se indica otra
        # cosa — para ejercitar la rama needs_weighing=True (cliente pidió
        # por UNIDADES un producto que se controla por kg) hay que forzar
        # uom_mode='unit' explícitamente después de crear la línea.
        order_a.order_line.uom_mode = 'unit'
        order_b.order_line.uom_mode = 'unit'

        session = self._create_session()
        session.action_load()

        self.assertEqual(session.state, 'loaded')
        self.assertEqual(len(session.line_ids), 3)

        line_a = session.line_ids.filtered(lambda l: l.sale_order_id == order_a)
        self.assertEqual(len(line_a), 1)
        self.assertEqual(line_a.main_customer_name, self.partner.name)
        self.assertEqual(line_a.zone_name, self.child_partner.name)
        self.assertEqual(line_a.estimated_kg, 5.0)
        self.assertTrue(line_a.needs_weighing)
        self.assertFalse(line_a.is_done)
        self.assertEqual(line_a.product_product_id, self.product_weight)

        line_b = session.line_ids.filtered(lambda l: l.sale_order_id == order_b)
        self.assertEqual(len(line_b), 1)
        # Sin parent_id: main_cust_name cae directo a partner.name, que
        # en este caso es el MISMO self.partner usado como order_id de b.
        self.assertEqual(line_b.main_customer_name, self.partner.name)
        self.assertEqual(line_b.estimated_kg, 2.0)
        self.assertTrue(line_b.needs_weighing)

        line_c = session.line_ids.filtered(lambda l: l.sale_order_id == order_c)
        self.assertEqual(len(line_c), 1)
        self.assertFalse(line_c.needs_weighing)
        self.assertEqual(line_c.estimated_kg, 3.0)
        self.assertEqual(line_c.product_product_id, self.product_unit)

        # Summary: product_weight agrega order_a (5kg) + order_b (2kg).
        summary_weight = session.summary_ids.filtered(
            lambda s: s.product_id == self.product_weight
        )
        self.assertEqual(len(summary_weight), 1)
        self.assertEqual(summary_weight.total_estimated_kg, 7.0)
        self.assertEqual(summary_weight.order_count, 2)
        self.assertEqual(summary_weight.total_done_kg, 0.0)

        summary_unit = session.summary_ids.filtered(
            lambda s: s.product_id == self.product_unit
        )
        self.assertEqual(len(summary_unit), 1)
        self.assertEqual(summary_unit.order_count, 1)
        self.assertEqual(summary_unit.total_estimated_kg, 3.0)

        # Claims del Nivel 1 (ist_preparation_day_picking): uno por
        # plantilla distinta, todos 'pending' (ninguna línea avanzada).
        claims = session.product_claim_ids
        self.assertEqual(len(claims), 2)
        self.assertEqual(set(claims.mapped('status')), {'pending'})
        self.assertEqual(
            set(claims.mapped('product_tmpl_id').ids),
            {
                self.product_weight.product_tmpl_id.id,
                self.product_unit.product_tmpl_id.id,
            },
        )

    def test_action_load_retroactive_update_on_second_call(self):
        """Rama de _guapante_add_order_lines() que actualiza
        main_customer_name/zone_name de una línea ya cargada (sin
        duplicarla) cuando cambia el partner de envío de la orden entre
        dos llamadas a action_load() — comportamiento que ya existía
        antes del refactor de e1 y debe seguir idéntico."""
        order = self._create_confirmed_order(
            product=self.product_weight, qty=4.0, partner=self.child_partner,
        )
        session = self._create_session()
        session.action_load()
        self.assertEqual(len(session.line_ids), 1)
        original_line_id = session.line_ids.id

        new_shipping = self.env['res.partner'].create({
            'name': 'Sucursal Nueva Test E1',
        })
        order.partner_shipping_id = new_shipping.id

        session.action_load()

        self.assertEqual(len(session.line_ids), 1)
        self.assertEqual(session.line_ids.id, original_line_id)
        self.assertEqual(session.line_ids.zone_name, 'Sucursal Nueva Test E1')
