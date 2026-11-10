# -*- coding: utf-8 -*-
"""Punto 3 (David, 2026-11-10): el chip de madurez tiene un color POR VALOR
(parámetro del sistema), no el índice aleatorio por producto."""
import re

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.misc import file_path

PARAM = 'ist_preparation_day_picking.attribute_chip_colors'


@tagged('post_install', '-at_install')
class TestAttributeChipsColor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attr = cls.env['product.attribute'].create({
            'name': 'Grado de Madurez (test)', 'create_variant': 'no_variant',
            'value_ids': [(0, 0, {'name': n}) for n in (
                'Verde', 'Maduro', 'Valor sin mapear')],
        })

    def _ptavs(self, template_name, native_color):
        tmpl = self.env['product.template'].create({
            'name': template_name,
            'attribute_line_ids': [(0, 0, {
                'attribute_id': self.attr.id,
                'value_ids': [(6, 0, self.attr.value_ids.ids)],
            })],
        })
        ptavs = tmpl.attribute_line_ids.product_template_value_ids
        ptavs.write({'color': native_color})
        return {p.product_attribute_value_id.name: p for p in ptavs}

    def _js(self):
        path = file_path(
            'ist_preparation_day_picking/static/src/js/'
            'preparation_picking_level2_display.js')
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_default_parameter_has_the_five_maturity_values(self):
        import json
        data = json.loads(self.env['ir.config_parameter'].get_param(PARAM))
        self.assertEqual(
            data, {'Verde': 10, 'Pinton': 3, 'Pinton-Maduro': 2,
                   'Maduro': 1, 'Cascara Negra': 0})

    def test_same_value_same_chip_color_in_different_products(self):
        a = self._ptavs('Producto A chips', native_color=5)
        b = self._ptavs('Producto B chips', native_color=9)
        self.assertEqual(a['Verde'].guapante_chip_color, 10)
        self.assertEqual(b['Verde'].guapante_chip_color, 10)
        self.assertEqual(a['Maduro'].guapante_chip_color, 1)
        self.assertEqual(b['Maduro'].guapante_chip_color, 1)

    def test_unmapped_value_is_neutral(self):
        a = self._ptavs('Producto C chips', native_color=7)
        self.assertEqual(a['Valor sin mapear'].guapante_chip_color, 0)

    def test_parameter_override_is_respected(self):
        self.env['ir.config_parameter'].set_param(PARAM, '{"Verde": 7}')
        a = self._ptavs('Producto D chips', native_color=2)
        self.assertEqual(a['Verde'].guapante_chip_color, 7)
        self.assertEqual(a['Maduro'].guapante_chip_color, 0)

    def test_invalid_parameter_leaves_chips_neutral_without_crashing(self):
        self.env['ir.config_parameter'].set_param(PARAM, 'no es json')
        a = self._ptavs('Producto E chips', native_color=4)
        self.assertEqual(a['Verde'].guapante_chip_color, 0)
        self.env['ir.config_parameter'].set_param(PARAM, '{"Verde": 99}')
        a['Verde'].invalidate_recordset()
        self.assertEqual(a['Verde'].guapante_chip_color, 0)

    def test_js_uses_the_per_value_color_not_the_random_one(self):
        js = self._js()
        self.assertNotIn('attr?.color', js)
        read = re.search(
            r'"product\.template\.attribute\.value",\s*attrIds,\s*\[([^\]]*)\]',
            js)
        self.assertTrue(read)
        self.assertIn('"guapante_chip_color"', read.group(1))
        self.assertNotIn('"color"', read.group(1))
        self.assertIn('attr?.guapante_chip_color', js)
