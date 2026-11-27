# -*- coding: utf-8 -*-
"""Q-10 (.332): un solo truncado a dos decimales para el XML y el CUNE. El punto flotante quitaba un centavo (166063.33 salía '166063.32')."""

import random

from odoo.addons.l10n_co_nomina_electronica.services import cune, dian_utils, montos, nomina_xml_builder
from odoo.tests.common import BaseCase, tagged


@tagged('post_install', '-at_install')
class TestMontosTruncado(BaseCase):

    def test_no_quita_el_centavo_y_sigue_truncando(self):
        for valor, esperado in ((166063.33, '166063.33'), (0.29, '0.29'), (4.35, '4.35'), (1500000, '1500000.00'), ('25000.5', '25000.50'),
                                (100.33999999999999, '100.34'),          # suma de líneas con error binario
                                ('25000.999', '25000.99'), (166063.339999, '166063.33'), (-4.35, '-4.35'),
                                (-0.001, '0.00'), (-0.0, '0.00'), (0, '0.00')):
            with self.subTest(valor=valor):
                self.assertEqual(montos.format_amount(valor), esperado)

    def test_ningun_valor_de_dos_decimales_cambia(self):
        generador = random.Random(332)
        for _i in range(20000):
            centavos = generador.randrange(0, 10 ** 12)
            self.assertEqual(montos.format_amount(centavos / 100), '%d.%02d' % (centavos // 100, centavos % 100))

    def test_el_xml_y_el_cune_usan_la_misma_funcion(self):
        self.assertIs(dian_utils.format_amount, montos.format_amount)
        self.assertIs(cune.format_amount, montos.format_amount)
        self.assertIs(nomina_xml_builder.format_amount, montos.format_amount)
        self.assertEqual(nomina_xml_builder._fmt(166063.33), '166063.33')
        self.assertEqual(nomina_xml_builder._fmt(None), '0.00')
        _cune, cadena = cune.compute_cune(
            num_ne='NE1', fec_ne='2026-09-30', hor_ne='10:00:00-05:00', val_dev=166063.33, val_ded=0.29, val_tol=4.35,
            nit_ne='900000000', doc_trab='1', cl_ne='102', tipo_amb='2', software_pin='1')
        self.assertIn('166063.330.294.35', cadena)
