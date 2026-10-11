# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Migración de datos existentes (UX-02, 2026-10-11, punto 3 de Tech Lead):
backfill de work_contact_id.vat para empleados que ya tienen identification_id
pero cuyo contacto todavía no tiene vat -- el caso real de 17 de los 18
empleados de Guapante (tienen tipo de identificación en Contactos, pero no
número).

Estándar de Odoo para esto: script de migración bajo migrations/<versión>/,
no post_init_hook -- post_init_hook solo corre en una instalación NUEVA del
módulo; este backfill es para una base YA instalada que sube de versión
(exactamente el caso de Guapante), así que debe correr en la actualización
(-u) que cruza por 18.0.3.0.89, el mecanismo nativo de Odoo para eso.

Solo rellena vat donde está VACÍO -- nunca sobreescribe un vat que ya tenga
algún valor (soporte_17/18: ninguno de los 18 tiene vat hoy, pero el filtro
protege igual contra cualquier dato real que exista para entonces).

NO se ejecuta solo con que este archivo exista en el repo: Odoo lo corre
automáticamente la próxima vez que el módulo se actualice (-u) en una base
cuya versión instalada sea anterior a 18.0.3.0.89 -- es decir, no antes de
que David autorice ese despliegue (ver protocolo del proyecto: "producción
no se usa para probar", CLAUDE.md).
"""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    empleados = env['hr.employee'].search([
        ('identification_id', '!=', False),
        ('work_contact_id', '!=', False),
        ('work_contact_id.vat', '=', False),
    ])
    for empleado in empleados:
        empleado.work_contact_id.sudo().vat = empleado.identification_id
