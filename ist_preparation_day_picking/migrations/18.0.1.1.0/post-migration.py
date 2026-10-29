# -*- coding: utf-8 -*-
"""Asigna el grupo nuevo "Administrador" (categoría Preparación) a Diana
y Mauricio — hoy tienen stock.group_stock_manager, de donde este alcance
tomaba prestado el permiso de los modelos de notas de Picking (Tech
Lead/QA, 2026-10-29).

Protegido por un parámetro de configuración, no solo por el versionado
de migraciones de Odoo: así es seguro invocar migrate() más de una vez
(a mano, en un test) sin deshacer que alguien quite el grupo después a
un usuario. Busca por login, no por id (distinto en cada base), y
tolera que no existan — en una base de pruebas o en otro cliente no debe
romper la instalación.
"""
from odoo import SUPERUSER_ID, api

_DONE_PARAM = 'ist_preparation_day_picking.migration_18_1_1_0_admin_grant_done'
_ADMIN_GROUP_XMLID = 'ist_preparation_day_picking.group_preparation_admin'
_LOGINS = [
    'tomatesguapante@gmail.com',  # Diana
    'mauriciobedoya2203@gmail.com',  # Mauricio
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    IrConfigParameter = env['ir.config_parameter'].sudo()
    if IrConfigParameter.get_param(_DONE_PARAM):
        return

    group = env.ref(_ADMIN_GROUP_XMLID, raise_if_not_found=False)
    if not group:
        return

    users = env['res.users'].search([('login', 'in', _LOGINS)])
    if users:
        users.write({'groups_id': [(4, group.id)]})

    IrConfigParameter.set_param(_DONE_PARAM, '1')
