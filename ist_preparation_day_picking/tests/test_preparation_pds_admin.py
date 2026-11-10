# -*- coding: utf-8 -*-
"""PDS administrativo (Pantalla B), Entrega 1: reportes 1 y 2 a pantalla
completa bajo «Pantallas», solo con el grupo «Reportes y PDS»."""
from odoo.api import call_kw
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

ACTIONS = {
    'action_pds_admin_operator': (
        'guapante.preparation.operator.report',
        'ist_preparation_day_picking.action_preparation_operator_report'),
    'action_pds_admin_interval': (
        'guapante.preparation.interval.report',
        'ist_preparation_day_picking.action_preparation_interval_report_2'),
}
MENUS = ['menu_pds_admin_operator', 'menu_pds_admin_interval']


@tagged('post_install', '-at_install')
class TestPreparationPdsAdmin(TransactionCase):

    def _user(self, login, groups):
        return self.env['res.users'].create({
            'name': login, 'login': login,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id] + [
                self.env.ref('ist_preparation_day_picking.' + g).id
                for g in groups])],
        })

    def test_server_actions_return_fullscreen_act_window_with_views(self):
        user = self._user('pds_reportes', ['group_preparation_reports_pds'])
        for xmlid, (model, source) in ACTIONS.items():
            server = self.env.ref('ist_preparation_day_picking.' + xmlid)
            action = server.with_user(user).run()
            self.assertEqual(action['type'], 'ir.actions.act_window')
            self.assertEqual(action['target'], 'fullscreen')
            self.assertEqual(action['res_model'], model)
            self.assertTrue(action['views'], 'orm/doAction exige `views`')
            origin = self.env['ir.actions.actions']._for_xml_id(source)
            self.assertEqual(action['views'], origin['views'])

    def test_menus_visible_only_with_reports_group(self):
        with_group = self._user('pds_con', ['group_preparation_reports_pds'])
        admin_only = self._user('pds_admin', ['group_preparation_admin'])
        for name in MENUS:
            menu = self.env.ref('ist_preparation_day_picking.' + name)
            self.assertIn(menu, self.env['ir.ui.menu'].with_user(with_group)
                          .search([('id', '=', menu.id)]))
            self.assertNotIn(menu, self.env['ir.ui.menu'].with_user(admin_only)
                             .search([('id', '=', menu.id)]))

    def test_admin_without_group_cannot_read_the_report_data(self):
        admin_only = self._user('pds_admin2', ['group_preparation_admin'])
        for model, _source in ACTIONS.values():
            with self.assertRaises(AccessError):
                call_kw(self.env[model].with_user(admin_only), 'search_count',
                        [[]], {})

    def test_menus_live_under_pantallas(self):
        root = self.env.ref('ist_preparation_day_picking.menu_pds_root')
        for name in MENUS:
            menu = self.env.ref('ist_preparation_day_picking.' + name)
            self.assertEqual(menu.parent_id, root)
