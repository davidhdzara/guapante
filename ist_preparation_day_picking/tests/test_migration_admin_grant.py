# -*- coding: utf-8 -*-
"""Asignación de "Administrador" (Preparación) a Diana y Mauricio por
login (Tech Lead/QA, 2026-10-29). Prueba la función compartida
(`hooks.grant_admin_group_once`) que usan tanto `post_init_hook`
(instalación nueva, ej. producción) como `migrations/18.0.1.1.0/
post-migration.py` (actualización de un módulo ya instalado, ej.
staging) — ambos caminos deben terminar en el mismo estado, sin
duplicar ni reinstalar a quien se quite el grupo después."""
import uuid
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ist_preparation_day_picking.hooks import (
    ADMIN_GRANT_DONE_PARAM,
    grant_admin_group_once,
    post_init_hook,
)

HOOKS_LOGINS_PATCH_TARGET = (
    'odoo.addons.ist_preparation_day_picking.hooks.ADMIN_GRANT_LOGINS'
)


@tagged('post_install', '-at_install')
class TestMigrationAdminGrant(TransactionCase):

    def setUp(self):
        super().setUp()
        self.group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin',
        )
        # Logins únicos por corrida (Tech Lead, 2026-10-29): los reales de
        # Diana/Mauricio ya existen en este staging — reutilizarlos choca
        # con la restricción de login único aunque la transacción del test
        # haga rollback al final, porque el choque es contra filas ya
        # confirmadas en la base. Se generan logins de prueba y se parchea
        # la lista que lee grant_admin_group_once para que los use.
        diana_login = f'diana.test.{uuid.uuid4().hex}@example.com'
        mauricio_login = f'mauricio.test.{uuid.uuid4().hex}@example.com'
        self._logins_patcher = patch(
            HOOKS_LOGINS_PATCH_TARGET, [diana_login, mauricio_login],
        )
        self._logins_patcher.start()
        self.addCleanup(self._logins_patcher.stop)

        # Este staging ya corrió la migración real alguna vez: el parámetro
        # "once" queda en '1' en la base real. Dentro de la transacción del
        # test (rollback al final) se borra para probar el comportamiento
        # de "primera vez", sin afectar el estado real fuera del test.
        self.env['ir.config_parameter'].sudo().search([
            ('key', '=', ADMIN_GRANT_DONE_PARAM),
        ]).unlink()

        self.diana = self.env['res.users'].create({
            'name': 'Diana Test', 'login': diana_login,
        })
        self.mauricio = self.env['res.users'].create({
            'name': 'Mauricio Test', 'login': mauricio_login,
        })

    def test_grant_adds_known_users_by_login(self):
        grant_admin_group_once(self.env)
        self.assertIn(self.group, self.diana.groups_id)
        self.assertIn(self.group, self.mauricio.groups_id)

    def test_grant_does_not_reinstate_manual_removal(self):
        """Correrla dos veces no debe reponer a quien se quitó a mano —
        protegido por el parámetro de configuración, no solo por el
        versionado de migraciones."""
        grant_admin_group_once(self.env)
        self.mauricio.write({'groups_id': [(3, self.group.id)]})

        grant_admin_group_once(self.env)

        self.assertNotIn(
            self.group, self.mauricio.groups_id,
            'La segunda corrida no debe volver a asignar a quien se quitó a mano',
        )
        self.assertIn(
            self.group, self.diana.groups_id,
            'A Diana, que nadie tocó, debe seguir asignada',
        )

    def test_grant_tolerates_missing_users(self):
        """En otra base (pruebas, otro cliente) esos logins no existen —
        no debe romper la instalación."""
        self.diana.unlink()
        self.mauricio.unlink()
        grant_admin_group_once(self.env)  # no debe lanzar excepción

    def test_post_init_hook_grants_on_fresh_install(self):
        """Caso producción: el módulo se instala de cero, nunca pasa por
        migrations/ — post_init_hook es el único camino, y debe dejar a
        ambos asignados igual que la migración."""
        post_init_hook(self.env)
        self.assertIn(self.group, self.diana.groups_id)
        self.assertIn(self.group, self.mauricio.groups_id)

    def test_hook_and_migration_together_do_not_duplicate_or_reinstate(self):
        """Si por lo que sea ambos caminos se invocan en la misma base
        (instalación nueva que además arrastra una actualización), no
        debe duplicar nada ni reinstalar a quien ya se quitó el grupo."""
        post_init_hook(self.env)
        self.mauricio.write({'groups_id': [(3, self.group.id)]})

        grant_admin_group_once(self.env)  # equivalente a correr la migración después

        self.assertNotIn(self.group, self.mauricio.groups_id)
        self.assertIn(self.group, self.diana.groups_id)

    def test_note_template_menu_has_only_admin_group(self):
        """QA (2026-10-29): el `groups` del <menuitem> es aditivo en una
        actualización — una versión anterior dejó este menú con
        stock.group_stock_manager (el préstamo de antes de la migración)
        PEGADO junto al grupo nuevo. Se corrigió con un record completo
        de ir.ui.menu + groups_id eval="[(6,0,...)]" — debe quedar con
        group_preparation_admin y nada más."""
        menu = self.env.ref(
            'ist_preparation_day_picking.menu_preparation_day_note_template',
        )
        self.assertEqual(menu.groups_id, self.group)
