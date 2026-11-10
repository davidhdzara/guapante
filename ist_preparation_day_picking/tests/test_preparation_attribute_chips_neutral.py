# -*- coding: utf-8 -*-
"""Punto 4 (2026-11-10): los chips de madurez/tamaño de Nivel 2 son neutros.
El `color` de product.template.attribute.value es aleatorio por producto
(verificado en producción), así que el JS no debe leerlo ni pintarlo."""
import re

from odoo.tools.misc import file_path
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAttributeChipsNeutral(TransactionCase):

    def _js(self):
        path = file_path(
            'ist_preparation_day_picking/static/src/js/'
            'preparation_picking_level2_display.js')
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_js_does_not_read_attribute_color(self):
        js = self._js()
        self.assertNotIn('attr?.color', js)
        read = re.search(
            r'"product\.template\.attribute\.value",\s*attrIds,\s*\[([^\]]*)\]',
            js)
        self.assertTrue(read, 'lectura de los valores de atributo')
        self.assertNotIn('"color"', read.group(1))

    def test_chip_color_is_always_neutral(self):
        self.assertIn('color: 0,', self._js())
