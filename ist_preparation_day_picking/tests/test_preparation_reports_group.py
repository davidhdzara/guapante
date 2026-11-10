# -*- coding: utf-8 -*-
"""Tema A (cliente vía David/Tech Lead, 2026-11-08): grupo «Reportes y
PDS» — los reportes y el PDS los ve SOLO quien lo tenga, aunque sea
Administrador de Preparación. Verifica la definición del grupo, que la
ficha de usuario NO se rompa (la categoría Preparación sigue siendo un
selector Operario < Administrador), y los menús de Reportes."""
from odoo.tests.common import TransactionCase, tagged

MENU_XMLIDS = [
    'menu_preparation_day_reports',
    'menu_preparation_operator_report',
    'menu_preparation_interval_report_2',
    'menu_preparation_interval_report_3',
    'menu_preparation_interval_report_4',
    'menu_preparation_interval_report_5',
]


@tagged('post_install', '-at_install')
class TestPreparationReportsGroup(TransactionCase):

    def setUp(self):
        super().setUp()
        self.reports_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_reports_pds',
        )
        self.admin_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin',
        )
        self.operator_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_picking_operator',
        )
        self.prep_category = self.env.ref(
            'ist_preparation_day_picking.module_category_preparation',
        )

    def test_group_has_own_category_and_no_implications(self):
        self.assertNotEqual(self.reports_group.category_id, self.prep_category)
        self.assertEqual(
            self.reports_group.category_id.name, 'Preparación — Reportes y PDS',
        )
        self.assertFalse(self.reports_group.implied_ids)
        self.assertNotIn(
            self.reports_group,
            (self.admin_group | self.operator_group).trans_implied_ids,
            'ni Administrador ni Operario deben dar el permiso de reportes',
        )

    def test_preparation_category_is_still_a_single_selector(self):
        """Si el grupo nuevo viviera en «Preparación», get_groups_by_
        application() la volvería casillas sueltas ('boolean'). Debe
        seguir siendo 'selection' ordenada Operario < Administrador."""
        found = False
        for entry in self.env['res.groups'].get_groups_by_application():
            app, kind, groups = entry[0], entry[1], entry[2]
            if app == self.prep_category:
                found = True
                self.assertEqual(kind, 'selection')
                self.assertEqual(
                    list(groups), [self.operator_group, self.admin_group],
                )
                self.assertNotIn(self.reports_group, groups)
        self.assertTrue(found, 'la categoría Preparación debe aparecer')

    def test_reports_group_has_its_own_entry_in_user_form(self):
        apps = {
            e[0]: e for e in self.env['res.groups'].get_groups_by_application()
        }
        entry = apps.get(self.reports_group.category_id)
        self.assertTrue(entry, 'debe aparecer como opción en la ficha del usuario')
        self.assertEqual(list(entry[2]), [self.reports_group])

    def test_reports_menus_only_for_reports_group(self):
        for xmlid in MENU_XMLIDS:
            menu = self.env.ref(f'ist_preparation_day_picking.{xmlid}')
            self.assertEqual(
                menu.groups_id, self.reports_group,
                f'{xmlid}: solo «Reportes y PDS», ni admin ni operario',
            )
