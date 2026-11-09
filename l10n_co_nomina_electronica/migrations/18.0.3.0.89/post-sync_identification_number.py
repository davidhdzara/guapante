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

.94 (2026-10-11, hallazgo de Tech Lead en producción, solo lectura): de los
18 empleados de Guapante, 16 contactos tienen tipo de identificación VAT
(genérico, el default de l10n_latam_base), 1 tiene NIT (Diana Cristina Gil
Posada, lo corrige RRHH a mano) y 1 ya tiene Cédula de ciudadanía. Sin
backfill, los 16 con VAT se quedarían sin código DIAN
(l10n_co_ne_dian_document_code) y ningún XML suyo podría generarse. Se
agrega un segundo backfill, mismo principio que el del número: solo toca el
caso VAT genérico -> Cédula de ciudadanía, nunca un contacto que ya tenga
NIT u otro tipo real asignado.

Importante para quien despliegue esto: este archivo vive en la carpeta
18.0.3.0.89 porque production nunca ha corrido la migración de esa versión
todavía (solo se probó sobre una copia de staging, que SÍ ya pasó por .89 --
en staging este backfill del tipo no se va a disparar solo por actualizar a
una versión posterior, Odoo no re-corre una carpeta de migración ya cruzada;
solo se vería ejecutándose la primera vez que PRODUCCIÓN suba de una versión
anterior a .89 hasta la que sea que David autorice).
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Backfill del NÚMERO (.89): identification_id -> work_contact_id.vat,
    # solo donde el contacto todavía no tiene ningún vat.
    empleados_sin_vat = env['hr.employee'].search([
        ('identification_id', '!=', False),
        ('work_contact_id', '!=', False),
        ('work_contact_id.vat', '=', False),
    ])
    for empleado in empleados_sin_vat:
        empleado.work_contact_id.sudo().vat = empleado.identification_id

    # Backfill del TIPO (.94): VAT genérico -> Cédula de ciudadanía, solo
    # para contactos de empleados de compañía colombiana, y solo cuando el
    # tipo actual es vacío o el genérico de l10n_latam_base -- nunca toca un
    # contacto con NIT u otro tipo real ya asignado.
    it_vat = env.ref('l10n_latam_base.it_vat', raise_if_not_found=False)
    cedula = env.ref('l10n_co.national_citizen_id', raise_if_not_found=False)
    tipos_actualizados = env['hr.employee']
    if it_vat and cedula:
        candidatos = env['hr.employee'].search([
            ('work_contact_id', '!=', False),
            ('company_id.partner_id.country_id.code', '=', 'CO'),
        ])
        tipos_actualizados = candidatos.filtered(
            lambda empleado: (
                not empleado.work_contact_id.l10n_latam_identification_type_id
                or empleado.work_contact_id.l10n_latam_identification_type_id == it_vat
            )
        )
        for empleado in tipos_actualizados:
            empleado.work_contact_id.sudo().l10n_latam_identification_type_id = cedula.id

    # Conflictos preexistentes del NÚMERO (empleados con identification_id
    # YA distinto del vat de su contacto, ambos con valor) -- la migración
    # nunca los toca (ver UX-02: nunca sobrescribe un valor ya distinto),
    # solo se registran en el log para que quede evidencia de lo que la
    # migración dejó sin resolver.
    conflictos = env['hr.employee'].search([
        ('identification_id', '!=', False),
        ('work_contact_id.vat', '!=', False),
    ]).filtered(
        lambda empleado: empleado.identification_id != empleado.work_contact_id.vat
    )

    _logger.info(
        'UX-02 migración 18.0.3.0.89: número rellenado en %s contacto(s); '
        'tipo actualizado de VAT genérico a Cédula de ciudadanía en %s '
        'contacto(s) (ids: %s); %s conflicto(s) preexistente(s) de número '
        'dejados sin tocar (ids de empleado: %s).',
        len(empleados_sin_vat),
        len(tipos_actualizados),
        tipos_actualizados.ids,
        len(conflictos),
        conflictos.ids,
    )
