# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Vistas del frente 3 (doc 53 §26, .211): se borra la vista heredada que ya no existe en el código.

.211 quitó del XML la vista ``view_payslip_form_ne_documento`` (la pestaña «DIAN» del recibo, que hereda
``hr_payroll.view_hr_payslip_form``) y del Python el campo ``hr.payslip.l10n_co_ne_intento_ids`` que esa vista usaba. En
una base que ya tenía la vista, Odoo valida la vista combinada del recibo ANTES de limpiar los registros huérfanos al
final de la actualización, y la vista vieja seguía nombrando el campo borrado (ParseError en ``view_payslip_form_ne``).
Se borra aquí, antes de cargar el módulo. Idempotente: sin la vista no hace nada."""

_MODULO = 'l10n_co_nomina_electronica'
_VISTAS_RETIRADAS = ('view_payslip_form_ne_documento',)


def migrate(cr, version):
    for nombre in _VISTAS_RETIRADAS:
        cr.execute("""
            DELETE FROM ir_model_data
             WHERE module = %s AND name = %s AND model = 'ir.ui.view'
         RETURNING res_id
        """, (_MODULO, nombre))
        for (vista_id,) in cr.fetchall():
            cr.execute('DELETE FROM ir_ui_view WHERE id = %s', (vista_id,))
