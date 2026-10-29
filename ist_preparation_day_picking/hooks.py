# -*- coding: utf-8 -*-
"""Asignación de "Administrador" (Preparación) a Diana y Mauricio —
una sola vez, sea que el módulo se instale de cero (post_init_hook,
caso producción) o se actualice desde una versión anterior
(migrations/18.0.1.1.0/post-migration.py, caso staging: QA, 2026-10-29
— los scripts de migrations/ solo corren al actualizar un módulo ya
instalado, nunca en una instalación nueva).

Ambos caminos llaman a la misma función, protegida por un parámetro de
configuración: invocarla más de una vez (desde el hook y la migración
a la vez, o a mano) nunca duplica ni reinstala a quien se quite el
grupo después."""

ADMIN_GRANT_DONE_PARAM = 'ist_preparation_day_picking.migration_18_1_1_0_admin_grant_done'
ADMIN_GROUP_XMLID = 'ist_preparation_day_picking.group_preparation_admin'
ADMIN_GRANT_LOGINS = [
    'tomatesguapante@gmail.com',  # Diana
    'mauriciobedoya2203@gmail.com',  # Mauricio
]


def grant_admin_group_once(env):
    IrConfigParameter = env['ir.config_parameter'].sudo()
    if IrConfigParameter.get_param(ADMIN_GRANT_DONE_PARAM):
        return

    group = env.ref(ADMIN_GROUP_XMLID, raise_if_not_found=False)
    if not group:
        return

    users = env['res.users'].search([('login', 'in', ADMIN_GRANT_LOGINS)])
    if users:
        users.write({'groups_id': [(4, group.id)]})

    IrConfigParameter.set_param(ADMIN_GRANT_DONE_PARAM, '1')


def post_init_hook(env):
    grant_admin_group_once(env)
