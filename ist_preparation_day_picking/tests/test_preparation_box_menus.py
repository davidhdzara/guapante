# -*- coding: utf-8 -*-
"""Regresión (2026-11-10): los menús de cajas del lote 4 deben conservar
nombre y padre al instalar el módulo de Picking (un <menuitem> sin name/parent
los dejó en la raíz con el xmlid como nombre)."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPreparationBoxMenus(TransactionCase):

    def test_box_menus_keep_name_parent_and_admin_group(self):
        root = self.env.ref('ist_preparation_day.menu_preparation_day_root')
        admin = self.env.ref('ist_preparation_day_picking.group_preparation_admin')
        expected = {
            'ist_preparation_day.menu_box_number_log': 'Historial de cajas',
            'ist_preparation_day.menu_box_number_issue': 'Inconsistencias de cajas',
        }
        for xmlid, name in expected.items():
            menu = self.env.ref(xmlid)
            self.assertEqual(menu.name, name)
            self.assertEqual(menu.parent_id, root)
            self.assertIn(admin, menu.groups_id)
            self.assertIn(self.env.ref('base.group_system'), menu.groups_id)

    def test_no_root_menu_is_named_like_an_xmlid(self):
        roots = self.env['ir.ui.menu'].with_context(
            ir_ui_menu_full_list=True).search([('parent_id', '=', False)])
        self.assertFalse([m.name for m in roots if m.name.startswith('ist_preparation')])
