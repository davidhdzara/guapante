# -*- coding: utf-8 -*-
"""Pantalla propia de Ajustes de Preparación (menú Preparación ›
Configuración › Ajustes, Tech Lead/David, 2026-11-02) — modelo
guapante.preparation.settings, TransientModel propio (no hereda
res.config.settings, ver docstring en models/preparation_settings.py).
Los dos campos (prep_idle_lock_enabled/prep_idle_lock_minutes) no son
una fuente de verdad nueva — son una traducción de IDLE_TIMEOUT_PARAM_KEY
(segundos), la misma que lee get_idle_timeout_seconds en todo Picking.
Estos tests cubren esa traducción en los dos sentidos y los permisos de
quién puede abrir/guardar esta pantalla sin pasar por base.group_system."""
import uuid

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged

from odoo.addons.ist_preparation_day.models.const_preparation import (
    IDLE_TIMEOUT_PARAM_KEY,
    get_idle_timeout_seconds,
)
from odoo.addons.ist_preparation_day.tests.test_preparation_day import (
    TestPreparationDay,
)


@tagged('post_install', '-at_install')
class TestPreparationSettingsIdleLock(TestPreparationDay):

    def _set_param(self, value):
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, value,
        )

    def _get_param(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            IDLE_TIMEOUT_PARAM_KEY,
        )

    def _settings(self):
        return self.env['guapante.preparation.settings'].create({})

    def test_defaults_disabled_shows_unchecked_with_fallback_minutes(self):
        self._set_param('0')
        settings = self._settings()
        self.assertFalse(settings.prep_idle_lock_enabled)
        self.assertEqual(settings.prep_idle_lock_minutes, 5)

    def test_defaults_300_seconds_shows_checked_5_minutes(self):
        self._set_param('300')
        settings = self._settings()
        self.assertTrue(settings.prep_idle_lock_enabled)
        self.assertEqual(settings.prep_idle_lock_minutes, 5)

    def test_defaults_90_seconds_falls_to_1_minute(self):
        """90s no es un múltiplo de 60 — se redondea hacia abajo y nunca
        por debajo de 1 minuto con la casilla marcada."""
        self._set_param('90')
        settings = self._settings()
        self.assertTrue(settings.prep_idle_lock_enabled)
        self.assertEqual(settings.prep_idle_lock_minutes, 1)

    def test_execute_checked_10_minutes_writes_600_seconds(self):
        self._set_param('0')
        settings = self._settings()
        settings.prep_idle_lock_enabled = True
        settings.prep_idle_lock_minutes = 10
        settings.execute()
        self.assertEqual(self._get_param(), '600')

    def test_execute_unchecked_writes_0(self):
        self._set_param('300')
        settings = self._settings()
        settings.prep_idle_lock_enabled = False
        settings.execute()
        self.assertEqual(self._get_param(), '0')

    def test_execute_without_changes_does_not_change_the_parameter(self):
        self._set_param('300')
        settings = self._settings()
        settings.execute()
        self.assertEqual(self._get_param(), '300')

    def test_execute_checked_zero_minutes_raises(self):
        self._set_param('300')
        settings = self._settings()
        settings.prep_idle_lock_minutes = 0
        with self.assertRaises(ValidationError):
            settings.execute()

    def test_execute_checked_over_1440_minutes_raises(self):
        self._set_param('300')
        settings = self._settings()
        settings.prep_idle_lock_minutes = 1441
        with self.assertRaises(ValidationError):
            settings.execute()

    def test_execute_checked_1440_minutes_is_allowed(self):
        """Límite superior inclusive — 1440 no debe reventar."""
        self._set_param('300')
        settings = self._settings()
        settings.prep_idle_lock_minutes = 1440
        settings.execute()
        self.assertEqual(self._get_param(), str(1440 * 60))

    def test_single_configuracion_menu_under_preparation_with_ajustes_child(self):
        """Hallazgo de Tech Lead (2026-11-02): "Configuración" ya existe
        (hr_employee_config_views.xml, con Operarios autorizados y
        Modelos de notas) — este menú NO debe crear un segundo
        "Configuración" bajo Preparación, solo colgar "Ajustes" del
        que ya hay."""
        root = self.env.ref('ist_preparation_day.menu_preparation_day_root')
        config_menus = self.env['ir.ui.menu'].search([
            ('name', '=', 'Configuración'),
            ('parent_id', '=', root.id),
        ])
        self.assertEqual(
            len(config_menus), 1,
            'Debe existir un solo menú "Configuración" bajo Preparación',
        )
        settings_menu = self.env.ref(
            'ist_preparation_day_picking.menu_preparation_settings',
        )
        self.assertEqual(settings_menu.parent_id, config_menus)


@tagged('post_install', '-at_install')
class TestPreparationSettingsPermissions(TestPreparationDay):
    """Objetivo explícito de este diseño (Tech Lead/David, 2026-11-02):
    un administrador de Preparación SIN base.group_system puede abrir y
    guardar esta pantalla; un operario sin ese grupo no."""

    def setUp(self):
        super().setUp()
        self.admin_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin',
        )
        self.operator_group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_picking_operator',
        )
        self.system_group = self.env.ref('base.group_system')
        self.internal_group = self.env.ref('base.group_user')

        self.prep_admin_user = self.env['res.users'].create({
            'name': 'Admin Preparación Test',
            'login': f'prep.admin.test.{uuid.uuid4().hex}@example.com',
            'groups_id': [(6, 0, [
                self.admin_group.id, self.internal_group.id,
            ])],
        })
        self.operator_user = self.env['res.users'].create({
            'name': 'Operario Test',
            'login': f'prep.operator.test.{uuid.uuid4().hex}@example.com',
            'groups_id': [(6, 0, [
                self.operator_group.id, self.internal_group.id,
            ])],
        })

    def test_admin_without_group_system_can_open_and_save(self):
        self.assertFalse(self.prep_admin_user.has_group('base.group_system'))
        self._set_param('0')
        settings = self.env['guapante.preparation.settings'].with_user(
            self.prep_admin_user,
        ).create({})
        settings.prep_idle_lock_enabled = True
        settings.prep_idle_lock_minutes = 7
        settings.execute()  # no debe lanzar
        self.assertEqual(self._get_param(), '420')

    def test_admin_save_is_reflected_by_get_idle_timeout_seconds(self):
        """Punto 4 de Tech Lead: no solo que guarde — que el resto de
        Picking (get_idle_timeout_seconds, usado por get_active_prep_
        operator_id y los claims) vea el valor que guardó este admin."""
        self._set_param('300')
        settings = self.env['guapante.preparation.settings'].with_user(
            self.prep_admin_user,
        ).create({})
        settings.prep_idle_lock_enabled = True
        settings.prep_idle_lock_minutes = 12
        settings.execute()
        self.assertEqual(get_idle_timeout_seconds(self.env), 720)

    def test_operator_cannot_create_the_settings_record(self):
        """ACL (ir.model.access.csv) — ni siquiera llega a execute()."""
        with self.assertRaises(AccessError):
            self.env['guapante.preparation.settings'].with_user(
                self.operator_user,
            ).create({})

    def test_operator_cannot_execute(self):
        """Aunque alguien le forzara un registro por sudo, execute()
        igual lo rechaza por el chequeo explícito de group_preparation_
        admin — doble barrera, no solo el ACL."""
        settings = self.env['guapante.preparation.settings'].sudo().create({})
        with self.assertRaises(AccessError):
            settings.with_user(self.operator_user).execute()

    def _set_param(self, value):
        self.env['ir.config_parameter'].sudo().set_param(
            IDLE_TIMEOUT_PARAM_KEY, value,
        )

    def _get_param(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            IDLE_TIMEOUT_PARAM_KEY,
        )
