# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""``data/neutralize.sql`` (doc 53 §23.15): una copia neutralizada de producción NUNCA debe transmitir a la
DIAN real. Calcado de ``l10n_co_dian/data/neutralize.sql`` (Facturación electrónica nativa): toda compañía
pasa al ambiente de Habilitación (Pruebas). No toca el proceso de certificación (la habilitación se hace en
staging)."""

from odoo.modules import neutralize
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNeutralize(TransactionCase):

    def _compania(self, nombre, ambiente, certificacion):
        return self.env['res.company'].create({
            'name': nombre, 'country_id': self.env.ref('base.co').id,
            'l10n_co_ne_environment': ambiente, 'l10n_co_ne_certification_process': certificacion})

    def test_odoo_descubre_el_archivo_del_modulo(self):
        consultas = list(neutralize.get_neutralization_queries(['l10n_co_nomina_electronica']))
        self.assertEqual(len(consultas), 1)
        self.assertIn('l10n_co_ne_environment', consultas[0])

    def test_toda_compania_queda_en_habilitacion_y_la_certificacion_no_se_toca(self):
        produccion = self._compania('Neutralizar Producción', '1', True)
        otra = self._compania('Neutralizar Otra', '1', False)
        self.assertEqual(produccion.l10n_co_ne_environment, '1')
        for consulta in neutralize.get_neutralization_queries(['l10n_co_nomina_electronica']):
            self.env.cr.execute(consulta)
        self.env.invalidate_all()
        self.assertEqual(produccion.l10n_co_ne_environment, '2')
        self.assertEqual(otra.l10n_co_ne_environment, '2')
        self.assertTrue(produccion.l10n_co_ne_certification_process)     # NO se toca
        self.assertFalse(otra.l10n_co_ne_certification_process)

    def test_una_compania_ya_en_habilitacion_no_cambia(self):
        compania = self._compania('Neutralizar Habilitación', '2', False)
        for consulta in neutralize.get_neutralization_queries(['l10n_co_nomina_electronica']):
            self.env.cr.execute(consulta)
        self.env.invalidate_all()
        self.assertEqual(compania.l10n_co_ne_environment, '2')
