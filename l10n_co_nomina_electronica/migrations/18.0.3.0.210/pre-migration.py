# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Estados del documento mensual: solo los 4 nativos (doc 53 §26b, .210).

``l10n_co_ne_documento.state`` y su related almacenado ``hr_payslip.l10n_co_ne_documento_state`` guardaban además
'draft', 'ready', 'uncertain' y 'eliminated', que ya viven en ``etapa``, ``incierto`` y ``eliminado``. Se dejan en NULL
ANTES de que Odoo quite esas opciones del Selection; la post-migración recalcula desde el último intento."""

_RETIRADOS = ('draft', 'ready', 'uncertain', 'eliminated')


def migrate(cr, version):
    for tabla, columna in (('l10n_co_ne_documento', 'state'), ('hr_payslip', 'l10n_co_ne_documento_state')):
        cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = %s AND column_name = %s AND table_schema = current_schema()
        """, (tabla, columna))
        if cr.fetchone():
            cr.execute('UPDATE "%s" SET "%s" = NULL WHERE "%s" IN %%s' % (tabla, columna, columna), (_RETIRADOS,))
