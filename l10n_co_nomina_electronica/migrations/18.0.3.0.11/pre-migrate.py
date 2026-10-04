# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Pre-migración 18.0.3.0.11 -- doc 23: limpieza de la vista huérfana
`view_payslip_form_account` (pestaña "Contabilidad" del payslip que
agregaba `journal_id`/`move_id`, definida en `views/hr_payroll_account_views.xml`,
eliminado en este ciclo junto con el motor contable propio que colisionaba
con `hr_payroll_account` nativo).

Quitar el archivo del manifest no limpia el `ir.ui.view` que había creado
en una instalación anterior -- queda vivo en la base con su `ir_model_data`.
Es una vista HEREDADA de `hr_payroll.view_hr_payslip_form`, misma categoría
de riesgo exacta que causó el `ParseError` de doc 16/19: Odoo revalida el
arch COMBINADO de una vista base apenas carga CUALQUIER OTRA vista
heredada de esa misma base -- una vista heredada huérfana referenciando
algo que ya no existe revienta esa revalidación.

Verificado por SSH en staging_produccion antes de escribir este script:
`hr_payroll.view_hr_payslip_form` la heredan, además de nosotros,
`hr_payroll_account`, `hr_payroll_account_iso20022`, `hr_payroll_attendance`,
`hr_payroll_expense`, `hr_payroll_holidays`, `hr_payroll_planning` y varios
módulos de localización -- todos instalados en este servidor. Un -u futuro
de cualquiera de esos módulos dispararía la revalidación combinada y
encontraría la vista huérfana si no se limpia ahora.

SQL directo (no ORM/env.ref()), mismo patrón ya usado en
18.0.3.0.3/pre-migrate.py (embargo híbrido) y 18.0.3.0.7/pre-migrate.py
(doc 19) para esta misma etapa temprana del -u.
"""

import logging

_logger = logging.getLogger(__name__)

_ORPHANED_VIEW_XMLID = 'view_payslip_form_account'


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
            'Pre-migración 18.0.3.0.11: no hay vista huérfana '
            '%s que limpiar (ya se limpió antes, o instalación nueva '
            'sin views/hr_payroll_account_views.xml nunca instalado).',
            _ORPHANED_VIEW_XMLID,
        )
        return

    imd_id, view_id = row
    cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (view_id,))
    cr.execute("DELETE FROM ir_model_data WHERE id = %s", (imd_id,))

    _logger.info(
        'Pre-migración 18.0.3.0.11: vista huérfana %s eliminada '
        '(ir_ui_view id: %s) antes de cargar datos del módulo -- '
        'evita que un -u futuro de otro módulo que herede '
        'hr_payroll.view_hr_payslip_form (ej. hr_payroll_account, '
        'hr_payroll_attendance, hr_payroll_expense, hr_payroll_holidays, '
        'hr_payroll_planning) dispare el mismo ParseError de doc 16/19.',
        _ORPHANED_VIEW_XMLID, view_id,
    )
