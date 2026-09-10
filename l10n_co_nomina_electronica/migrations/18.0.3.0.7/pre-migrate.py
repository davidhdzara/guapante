# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Pre-migración 18.0.3.0.7 -- limpieza de la vista huérfana
`view_company_form_ne` (doc 19: la config de Nómina Electrónica se mueve
de una pestaña en la ficha de la compañía a Ajustes > Nómina).

Quitar `views/res_company_views.xml` del manifest no limpia el
`ir.ui.view` que ese archivo había creado en una instalación anterior --
queda vivo en la base con su `ir_model_data`. Es una vista HEREDADA de
`base.view_company_form`, misma categoría de riesgo exacta que causó el
`ParseError` de doc 16 (embargo híbrido): Odoo revalida el arch COMBINADO
de una vista base apenas carga CUALQUIER OTRA vista heredada de esa misma
base -- una vista heredada huérfana referenciando algo que ya no existe
revienta esa revalidación.

A diferencia de doc 16, en este ciclo `l10n_co_nomina_electronica` ya no
tiene NINGUNA otra vista heredando `base.view_company_form` (este era la
única) -- nuestra propia instalación no dispararía el bug. Pero Tech Lead
verificó por SSH que otro módulo instalado en el mismo servidor SÍ hereda
esa misma vista base:

    grep -rl 'base.view_company_form' /home/odoo/src/user/*/views/*.xml
    -> l10n_co_bank_payment_export/views/res_bank_views.xml
    -> l10n_co_nomina_electronica/views/res_company_views.xml

Si en el futuro ese módulo (`l10n_co_bank_payment_export`) recibe su
propio `-u`, por cualquier motivo ajeno a nosotros, la revalidación
combinada se dispararía igual y encontraría `view_company_form_ne`
huérfana -- mismo `ParseError` de doc 16, en un momento y por una causa
que no controlamos. Se limpia ahora para no dejar esa bomba de tiempo.

SQL directo (no ORM/env.ref()), mismo patrón ya usado en
`18.0.3.0.3/pre-migrate.py` (embargo híbrido) para esta misma etapa
temprana del `-u`.
"""

import logging

_logger = logging.getLogger(__name__)

_ORPHANED_VIEW_XMLID = 'view_company_form_ne'


def migrate(cr, version):
    cr.execute("""
        SELECT id, res_id FROM ir_model_data
        WHERE module = 'l10n_co_nomina_electronica'
          AND name = %s
          AND model = 'ir.ui.view'
    """, (_ORPHANED_VIEW_XMLID,))
    row = cr.fetchone()
    if not row:
        _logger.info(
            'Pre-migración 18.0.3.0.7: no hay vista huérfana '
            '%s que limpiar (ya se limpió antes, o instalación nueva '
            'sin views/res_company_views.xml nunca instalado).',
            _ORPHANED_VIEW_XMLID,
        )
        return

    imd_id, view_id = row
    cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (view_id,))
    cr.execute("DELETE FROM ir_model_data WHERE id = %s", (imd_id,))

    _logger.info(
        'Pre-migración 18.0.3.0.7: vista huérfana %s eliminada '
        '(ir_ui_view id: %s) antes de cargar datos del módulo -- '
        'evita que un -u futuro de otro módulo que herede '
        'base.view_company_form (ej. l10n_co_bank_payment_export) '
        'dispare el mismo ParseError de doc 16.',
        _ORPHANED_VIEW_XMLID, view_id,
    )
