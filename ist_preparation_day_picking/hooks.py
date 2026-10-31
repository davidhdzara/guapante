# -*- coding: utf-8 -*-
"""Asignación de grupos de Preparación — una sola vez cada una, sea que
el módulo se instale de cero (post_init_hook, caso producción) o se
actualice desde una versión anterior (migrations/, caso staging: QA,
2026-10-29 — los scripts de migrations/ solo corren al actualizar un
módulo ya instalado, nunca en una instalación nueva).

Cada asignación (Administrador a Diana/Mauricio, Operario al usuario
compartido del tablet) tiene su PROPIO parámetro "once" — invocar
cualquiera más de una vez (desde el hook y la migración a la vez, o a
mano) nunca duplica ni reinstala a quien se quite el grupo después.

Bloqueante real encontrado por Tech Lead antes de la salida a
producción (2026-10-31): en una instalación nueva (producción), el
grupo "Operario de Picking" nace SIN ningún usuario — post_init_hook
solo daba Administrador a Diana/Mauricio. El usuario compartido del
tablet (operacion@donguapante.com) se queda sin el grupo, sin ver el
menú de Picking y sin ACL sobre claims/wizards — el NIP nunca llega a
importar porque no se puede ni abrir la pantalla. En staging esto
"funcionaba" porque ese usuario ya tenía el grupo de una versión
anterior del módulo, antes de que existiera este hook."""

ADMIN_GRANT_DONE_PARAM = 'ist_preparation_day_picking.migration_18_1_1_0_admin_grant_done'
ADMIN_GROUP_XMLID = 'ist_preparation_day_picking.group_preparation_admin'
ADMIN_GRANT_LOGINS = [
    'tomatesguapante@gmail.com',  # Diana
    'mauriciobedoya2203@gmail.com',  # Mauricio
]

OPERATOR_GRANT_DONE_PARAM = 'ist_preparation_day_picking.migration_18_1_3_0_operator_grant_done'
OPERATOR_GROUP_XMLID = 'ist_preparation_day_picking.group_preparation_picking_operator'
OPERATOR_GRANT_LOGINS = [
    'operacion@donguapante.com',  # tablet compartido de Picking
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


def grant_operator_group_once(env):
    IrConfigParameter = env['ir.config_parameter'].sudo()
    if IrConfigParameter.get_param(OPERATOR_GRANT_DONE_PARAM):
        return

    group = env.ref(OPERATOR_GROUP_XMLID, raise_if_not_found=False)
    if not group:
        return

    users = env['res.users'].search([('login', 'in', OPERATOR_GRANT_LOGINS)])
    if users:
        users.write({'groups_id': [(4, group.id)]})

    IrConfigParameter.set_param(OPERATOR_GRANT_DONE_PARAM, '1')


def post_init_hook(env):
    grant_admin_group_once(env)
    grant_operator_group_once(env)
