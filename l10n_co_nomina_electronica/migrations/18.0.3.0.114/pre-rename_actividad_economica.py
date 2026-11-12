# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Pre-migración (.114): hr.contract.l10n_co_pila_actividad_economica pasa de Char a Many2one
(catálogo del Decreto 768 de 2022, l10n.co.pila.ciiu).

Odoo no convierte una columna varchar en una llave foránea entera al actualizar el módulo, así
que ANTES de cargar el modelo se renombra la columna vieja a ..._legacy; el ORM crea la columna
nueva (integer) con el nombre original y el post-script mapea el texto viejo al catálogo.
Idempotente: solo renombra si la columna actual es de texto y todavía no existe la legacy.
"""

import logging

_logger = logging.getLogger(__name__)

_TABLA = 'hr_contract'
_COLUMNA = 'l10n_co_pila_actividad_economica'
_LEGACY = _COLUMNA + '_legacy'


def migrate(cr, version):
    cr.execute(
        """SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = %s AND column_name IN (%s, %s)""",
        (_TABLA, _COLUMNA, _LEGACY))
    columnas = dict(cr.fetchall())
    if columnas.get(_COLUMNA) in ('character varying', 'text') and _LEGACY not in columnas:
        cr.execute('ALTER TABLE %s RENAME COLUMN %s TO %s' % (_TABLA, _COLUMNA, _LEGACY))
        _logger.info('hr_contract.%s renombrada a %s antes de pasar a Many2one.', _COLUMNA, _LEGACY)
