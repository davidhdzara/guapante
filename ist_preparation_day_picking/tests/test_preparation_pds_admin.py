# -*- coding: utf-8 -*-
"""PDS administrativo (Pantalla B): reportes 1 y 2 a pantalla completa bajo
«Pantallas», con refresco automático (entrega 2), solo con «Reportes y PDS»."""
from odoo.api import call_kw
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.misc import file_path

PARAM = 'ist_preparation_day_picking.pds_admin_refresh_minutes'
ACTIONS = {
    'action_pds_admin_operator':
        'ist_preparation_day_picking.action_preparation_operator_report',
    'action_pds_admin_interval':
        'ist_preparation_day_picking.action_preparation_interval_report_2',
}
MENUS = ['menu_pds_admin_operator', 'menu_pds_admin_interval']
REPORT_MODELS = [
    'guapante.preparation.operator.report',
    'guapante.preparation.interval.report',
]


@tagged('post_install', '-at_install')
class TestPreparationPdsAdmin(TransactionCase):

    def _user(self, login, groups):
        return self.env['res.users'].create({
            'name': login, 'login': login,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id] + [
                self.env.ref('ist_preparation_day_picking.' + g).id
                for g in groups])],
        })

    def _js(self):
        with open(file_path(
                'ist_preparation_day_picking/static/src/js/'
                'preparation_pds_admin.js'), encoding='utf-8') as fh:
            return fh.read()

    # ── acciones y menús ──

    def test_client_actions_point_to_existing_report_actions(self):
        for xmlid, source in ACTIONS.items():
            action = self.env.ref('ist_preparation_day_picking.' + xmlid)
            self.assertEqual(action.type, 'ir.actions.client')
            self.assertEqual(action.tag, 'guapante_pds_admin')
            self.assertEqual(action.target, 'fullscreen')
            self.assertIn(source, action.context)
            # la acción de origen existe y trae `views` (el JS la carga)
            origin = self.env['ir.actions.actions']._for_xml_id(source)
            self.assertTrue(origin['views'])

    def test_menus_visible_only_with_reports_group(self):
        with_group = self._user('pds_con', ['group_preparation_reports_pds'])
        admin_only = self._user('pds_admin', ['group_preparation_admin'])
        for name in MENUS:
            menu = self.env.ref('ist_preparation_day_picking.' + name)
            self.assertIn(menu, self.env['ir.ui.menu'].with_user(with_group)
                          .search([('id', '=', menu.id)]))
            self.assertNotIn(menu, self.env['ir.ui.menu'].with_user(admin_only)
                             .search([('id', '=', menu.id)]))

    def test_menus_live_under_pantallas(self):
        root = self.env.ref('ist_preparation_day_picking.menu_pds_root')
        for name in MENUS:
            menu = self.env.ref('ist_preparation_day_picking.' + name)
            self.assertEqual(menu.parent_id, root)

    def test_admin_without_group_cannot_read_the_report_data(self):
        admin_only = self._user('pds_admin2', ['group_preparation_admin'])
        for model in REPORT_MODELS:
            with self.assertRaises(AccessError):
                call_kw(self.env[model].with_user(admin_only), 'search_count',
                        [[]], {})

    # ── intervalo de refresco (call_kw, como lo llama el JS) ──

    def _minutes(self, user):
        return call_kw(
            self.env['guapante.preparation.day'].with_user(user),
            'get_pds_admin_refresh_minutes', [], {})

    def test_refresh_minutes_default_is_five(self):
        user = self._user('pds_min1', ['group_preparation_reports_pds'])
        self.assertEqual(self.env['ir.config_parameter'].get_param(PARAM), '5')
        self.assertEqual(self._minutes(user), 5)

    def test_refresh_minutes_respects_parameter_and_clamps(self):
        user = self._user('pds_min2', ['group_preparation_reports_pds'])
        Param = self.env['ir.config_parameter']
        for raw, expected in (
                ('10', 10), ('0', 1), ('-3', 1), ('1', 1),
                ('99999', 60), ('abc', 5), ('', 5), ('2.9', 2)):
            Param.set_param(PARAM, raw)
            self.assertEqual(self._minutes(user), expected, raw)

    def test_refresh_minutes_requires_reports_group(self):
        admin_only = self._user('pds_min3', ['group_preparation_admin'])
        with self.assertRaises(AccessError):
            self._minutes(admin_only)

    # ── JS (verificación de código: no hay navegador en la suite) ──

    def test_js_clears_timer_and_handles_expired_session(self):
        js = self._js()
        self.assertIn('onWillUnmount', js)
        self.assertIn('window.clearInterval', js)
        self.assertEqual(js.count('window.setInterval'), 1)
        self.assertIn('odoo.http.SessionExpiredException', js)
        self.assertIn('this._stop();', js)
        self.assertIn('get_pds_admin_refresh_minutes', js)
        self.assertIn('actionId: false', js)
