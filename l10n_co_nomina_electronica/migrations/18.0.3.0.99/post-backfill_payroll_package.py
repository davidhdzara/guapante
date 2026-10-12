# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Migración de datos existentes ("Localización nómina", .99, pedido de
David): backfill de res.company.l10n_co_ne_payroll_package para la(s)
compañía(s) colombianas ya existentes (ej. Guapante) -- el campo es nuevo,
sin este backfill una base YA instalada quedaría con "Paquete" vacío en
Ajustes > Nómina hasta que alguien lo elija a mano.

Estándar de Odoo para esto: script de migración bajo migrations/<versión>/
(mismo patrón que migrations/18.0.3.0.89/post-sync_identification_number.py),
no post_init_hook -- este backfill es para una base YA instalada que sube
de versión, debe correr en la actualización (-u) que cruza por 18.0.3.0.99.

Idempotente: solo rellena donde el campo está VACÍO, nunca sobreescribe un
valor ya elegido (hoy solo existe la opción 'l10n_co_nomina_electronica',
pero el filtro protege igual si en el futuro alguien lo cambia a mano o
InSoTech agrega otro paquete).

NO se ejecuta solo con que este archivo exista en el repo: Odoo lo corre
automáticamente la próxima vez que el módulo se actualice (-u) en una base
cuya versión instalada sea anterior a 18.0.3.0.99 -- no antes de que David
autorice ese despliegue (CLAUDE.md: "producción no se usa para probar").
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_PACKAGE_CODE = 'l10n_co_nomina_electronica'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    companias = env['res.company'].search([
        ('partner_id.country_id.code', '=', 'CO'),
        ('l10n_co_ne_payroll_package', '=', False),
    ])
    companias.write({'l10n_co_ne_payroll_package': _PACKAGE_CODE})

    _logger.info(
        'Localización nómina migración 18.0.3.0.99: paquete "%s" asignado '
        'a %s compañía(s) colombiana(s) sin paquete previo (ids: %s).',
        _PACKAGE_CODE, len(companias), companias.ids,
    )
