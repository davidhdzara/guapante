# -*- coding: utf-8 -*-
"""Migración 18.0.1.1.0 (Tech Lead/QA, 2026-10-29): asigna el grupo
"Administrador" (Preparación) a Diana y Mauricio por login, una sola
vez. Carga el script directamente desde su archivo — no es parte del
paquete Python del módulo, Odoo lo ejecuta por ruta durante el upgrade —
para poder probar su idempotencia sin depender del motor de versiones
de Odoo."""
import importlib.util
import os

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged


def _load_migrate():
    script_path = os.path.join(
        get_module_path('ist_preparation_day_picking'),
        'migrations', '18.0.1.1.0', 'post-migration.py',
    )
    spec = importlib.util.spec_from_file_location(
        'ist_preparation_day_picking_post_migration_18_1_1_0', script_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged('post_install', '-at_install')
class TestMigrationAdminGrant(TransactionCase):

    def setUp(self):
        super().setUp()
        self.migrate = _load_migrate()
        self.group = self.env.ref(
            'ist_preparation_day_picking.group_preparation_admin',
        )
        self.diana = self.env['res.users'].create({
            'name': 'Diana Test', 'login': 'tomatesguapante@gmail.com',
        })
        self.mauricio = self.env['res.users'].create({
            'name': 'Mauricio Test', 'login': 'mauriciobedoya2203@gmail.com',
        })

    def test_migration_adds_known_users_by_login(self):
        self.migrate(self.env.cr, '18.0.1.1.0')
        self.assertIn(self.group, self.diana.groups_id)
        self.assertIn(self.group, self.mauricio.groups_id)

    def test_migration_does_not_reinstate_manual_removal(self):
        """Correrla dos veces no debe reponer a quien se quitó a mano —
        protegido por el parámetro de configuración, no solo por el
        versionado de migraciones (QA, 2026-10-29)."""
        self.migrate(self.env.cr, '18.0.1.1.0')
        self.mauricio.write({'groups_id': [(3, self.group.id)]})

        self.migrate(self.env.cr, '18.0.1.1.0')

        self.assertNotIn(
            self.group, self.mauricio.groups_id,
            'La segunda corrida no debe volver a asignar a quien se quitó a mano',
        )
        self.assertIn(
            self.group, self.diana.groups_id,
            'A Diana, que nadie tocó, debe seguir asignada',
        )

    def test_migration_tolerates_missing_users(self):
        """En otra base (pruebas, otro cliente) esos logins no existen —
        no debe romper la instalación."""
        self.diana.unlink()
        self.mauricio.unlink()
        self.migrate(self.env.cr, '18.0.1.1.0')  # no debe lanzar excepción
