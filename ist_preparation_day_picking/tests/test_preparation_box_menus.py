# -*- coding: utf-8 -*-
"""Regresión (2026-11-10): los menús de cajas del lote 4 deben conservar
nombre y padre al instalar el módulo de Picking (un <menuitem> sin name/parent
los dejó en la raíz con el xmlid como nombre)."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPreparationBoxMenus(TransactionCase):

    def test_box_menus_keep_name_parent_and_admin_group(self):
        admin_menu = self.env.ref('ist_preparation_day.menu_preparation_admin')
        admin = self.env.ref('ist_preparation_day_picking.group_preparation_admin')
        expected = {
            'ist_preparation_day.menu_box_number_log': 'Historial de cajas',
            'ist_preparation_day.menu_box_number_issue': 'Inconsistencias de cajas',
        }
        for xmlid, name in expected.items():
            menu = self.env.ref(xmlid)
            self.assertEqual(menu.name, name)
            self.assertEqual(menu.parent_id, admin_menu)
            self.assertIn(admin, menu.groups_id)
            self.assertIn(self.env.ref('base.group_system'), menu.groups_id)

    def test_no_root_menu_is_named_like_an_xmlid(self):
        roots = self.env['ir.ui.menu'].with_context(
            ir_ui_menu_full_list=True).search([('parent_id', '=', False)])
        self.assertFalse([m.name for m in roots if m.name.startswith('ist_preparation')])

    def test_admin_tools_are_grouped_under_administracion(self):
        """Tech Lead/David 2026-11-10: las herramientas de administrador viven
        bajo UN menú «Administración», no como pestañas sueltas de la barra."""
        admin_menu = self.env.ref('ist_preparation_day.menu_preparation_admin')
        self.assertEqual(admin_menu.name, 'Administración')
        self.assertEqual(
            admin_menu.parent_id,
            self.env.ref('ist_preparation_day.menu_preparation_day_root'))
        group = self.env.ref('ist_preparation_day_picking.group_preparation_admin')
        self.assertIn(group, admin_menu.groups_id)
        self.assertIn(self.env.ref('base.group_system'), admin_menu.groups_id)
        for xmlid in (
                'ist_preparation_day_picking.menu_claim_stopped',
                'ist_preparation_day.menu_box_number_log',
                'ist_preparation_day.menu_box_number_issue'):
            self.assertEqual(self.env.ref(xmlid).parent_id, admin_menu, xmlid)

    def test_root_menu_has_only_the_expected_first_level_entries(self):
        root = self.env.ref('ist_preparation_day.menu_preparation_day_root')
        names = set(self.env['ir.ui.menu'].sudo().search(
            [('parent_id', '=', root.id)]).mapped('name'))
        self.assertEqual(names, {
            'Sesiones', 'Pantallas', 'Reportes', 'Administración',
            'Configuración'})

    def test_administracion_visible_to_prep_admin_and_hidden_from_operator(self):
        admin_menu = self.env.ref('ist_preparation_day.menu_preparation_admin')
        Users = self.env['res.users']
        def make(login, xmlid):
            return Users.create({
                'name': login, 'login': login,
                'groups_id': [(6, 0, [
                    self.env.ref('base.group_user').id,
                    self.env.ref(xmlid).id])]})
        admin = make('adm_menu_t', 'ist_preparation_day_picking.group_preparation_admin')
        operator = make('op_menu_t', 'ist_preparation_day_picking.group_preparation_picking_operator')
        Menu = self.env['ir.ui.menu']
        self.assertIn(admin_menu, Menu.with_user(admin).search([('id', '=', admin_menu.id)]))
        self.assertNotIn(admin_menu, Menu.with_user(operator).search([('id', '=', admin_menu.id)]))
