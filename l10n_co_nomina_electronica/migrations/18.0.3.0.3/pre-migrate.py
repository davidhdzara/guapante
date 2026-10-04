# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Pre-migración 18.0.3.0.3 — limpieza de las 4 vistas huérfanas de
`hr_embargo_views.xml` (embargo híbrido, doc 16), ANTES de que se cargue
cualquier dato del módulo.

Encontrado por Tech Lead corriendo el `-u` real contra staging_produccion:
quitar `views/hr_embargo_views.xml` del manifest no limpia los 4
`ir.ui.view` que ese archivo había creado en una instalación anterior --
quedan vivos en la base con su `ir_model_data`. Uno de ellos,
`view_employee_form_embargo`, es una vista HEREDADA de
`hr.view_employee_form` que todavía referencia el campo `l10n_co_embargo_ids`
(eliminado de `hr.employee` en este mismo ciclo). Apenas Odoo intenta
cargar/validar CUALQUIER otra vista heredada de `hr.view_employee_form`
(en este caso la propia `hr_employee_views.xml` del módulo,
`view_employee_form_ne`), revalida el arch COMBINADO de todas las vistas
activas de ese formulario -- incluida la huérfana -- y truena:

    ParseError: Field "l10n_co_embargo_ids" does not exist in model "hr.employee"
    xmlid: view_employee_form_ne  (el mensaje señala a la vista que disparó
                                    la revalidación, no a la vista culpable)

Es la MISMA causa raíz que el bug de tablas huérfanas de 18.0.3.0.1 (quitar
un archivo/modelo del manifest no dispara su limpieza automática), pero acá
el efecto es distinto: no es deuda silenciosa, es un bloqueo duro de la
instalación completa. Y por eso corre en PRE-migrate, no post-migrate:
`ir.model.data._process_end()` (el barrido estándar de "ya no declarado en
este módulo") sólo corre al FINAL de cargar todos los datos del módulo --
para entonces el ParseError de arriba ya habría ocurrido durante la carga
de `hr_employee_views.xml`. Hace falta borrar las 4 vistas ANTES de que
empiece esa carga.

SQL directo (no ORM/env.ref()) -- mismo patrón ya usado en
`18.0.2.1.0/pre-migrate.py` para esta misma etapa temprana del `-u`, antes
de que el registro de modelos/vistas esté en un estado predecible para
usar el ORM con confianza.
"""

import logging

_logger = logging.getLogger(__name__)

_ORPHANED_VIEW_XMLIDS = (
    'view_l10n_co_hr_embargo_form',
    'view_l10n_co_hr_embargo_list',
    'view_l10n_co_hr_embargo_search',
    'view_employee_form_embargo',
)


def migrate(cr, version):
    cr.execute("""
        SELECT id, res_id FROM ir_model_data
        WHERE module = 'l10n_co_nomina_electronica'
          AND name IN %s
          AND model = 'ir.ui.view'
    """, (_ORPHANED_VIEW_XMLIDS,))
    rows = cr.fetchall()
    if not rows:
        _logger.info(
            'Pre-migración 18.0.3.0.3: no hay vistas huérfanas de '
            'hr_embargo_views.xml que limpiar (ya se limpiaron antes, o '
            'instalación nueva sin ese archivo nunca instalado).'
        )
        return

    imd_ids = [row[0] for row in rows]
    view_ids = [row[1] for row in rows]

    cr.execute("DELETE FROM ir_ui_view WHERE id IN %s", (tuple(view_ids),))
    cr.execute("DELETE FROM ir_model_data WHERE id IN %s", (tuple(imd_ids),))

    _logger.info(
        'Pre-migración 18.0.3.0.3: %d vista(s) huérfana(s) de '
        'hr_embargo_views.xml eliminadas (ir_ui_view ids: %s) antes de '
        'cargar datos del módulo -- bloqueaban la validación del arch '
        'combinado de hr.view_employee_form.',
        len(view_ids), view_ids,
    )
