# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestRetentionCategory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category_model = cls.env['insotech.retention.category']
        cls.country_co = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)

    def test_01_auto_generate_categories(self):
        """ Prueba la generación automática de jerarquías DANE """
        if not self.country_co:
            self.skipTest("País CO no encontrado en la base de datos de pruebas.")

        # Limpiar categorías existentes para prueba limpia (si la política lo permite)
        self.category_model.search([]).unlink()

        # Ejecutar generación
        self.category_model.auto_generate_colombian_dane_categories()

        # Verificar raíces
        nacionales = self.category_model.search([('name', '=', 'Nacionales')])
        self.assertEqual(len(nacionales), 1, "Debe existir la carpeta Nacionales")
        
        departamentales = self.category_model.search([('name', '=', 'Departamentales')])
        self.assertEqual(len(departamentales), 1, "Debe existir la carpeta Departamentales")

        # Verificar departamentos y ciudades si existían en los maestros
        states = self.env['res.country.state'].search([('country_id', '=', self.country_co.id)])
        if states:
            state_cats = self.category_model.search([('parent_id', '=', departamentales.id)])
            self.assertEqual(len(state_cats), len(states), "Deben existir tantas carpetas de departamentos como estados de CO")
