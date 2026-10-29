# -*- coding: utf-8 -*-
"""Asignación de "Administrador" (Preparación) a Diana y Mauricio por
login (Tech Lead/QA, 2026-10-29). Prueba la función compartida
(`hooks.grant_admin_group_once`) que usan tanto `post_init_hook`
(instalación nueva, ej. producción) como `migrations/18.0.1.1.0/
post-migration.py` (actualización de un módulo ya instalado, ej.
staging) — ambos caminos deben terminar en el mismo estado, sin
duplicar ni reinstalar a quien se quite el grupo después."""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ist_preparation_day_picking.hooks import (
    grant_admin_group_once,
    post_init_hook,
)


@tagged('post_install', '-at_install')
class TestMigrationAdminGrant(TransactionCase):

    def setUp(self):
        super().setUp()
        self.group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin',
        )
        self.diana = self.env['res.users'].create({
            'name': 'Diana Test', 'login': 'tomatesguapante@gmail.com',
        })
        self.mauricio = self.env['res.users'].create({
            'name': 'Mauricio Test', 'login': 'mauriciobedoya2203@gmail.com',
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
