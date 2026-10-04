# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Post-migración 18.0.3.0.1 — DROP TABLE explícito de los modelos eliminados
en 18.0.3.0.0 (annual_params/time_params -> hr.rule.parameter, doc 13).

Por qué hace falta un fix aparte (no bastó con el post-migrate de
18.0.3.0.0): verificado por Tech Lead directo en `staging_produccion` tras
el deploy real -- las tablas `l10n_co_payroll_annual_params` (3 filas) y
`l10n_co_payroll_time_params` (4 filas) seguían existiendo pese a que doc
13 asumía que el mecanismo estándar de `-u` (`ir.model._process_end` +
`ir.model.unlink()` -> `_drop_table()`) las limpiaba automáticamente.

Causa raíz exacta (confirmada leyendo `ir_model.py` línea 326-345,
`IrModel._drop_table()`, en el servidor):

    current_model = self.env.get(model.model)
    if current_model is not None:
        ... DROP TABLE ... CASCADE ...
    else:
        _logger.runbot('...no se pudo eliminar porque no existe en el '
                        'registro.')

`_drop_table()` solo ejecuta el DROP si el modelo TODAVÍA existe en el
registro de Python. Eso es cierto cuando solo se quita un CAMPO de un
modelo que sigue vivo (por eso `l10n_co_retefuente_uvt.annual_params_id`
sí se limpió bien) -- pero cuando se borra el MODELO COMPLETO, para
cuando `_process_end()` corre (al final de `-u`, ya con el código nuevo
cargado) la clase Python ya no existe en el registro, cae al `else`, y el
DROP TABLE nunca se ejecuta. Solo queda un log nivel `runbot` (ni
siquiera WARNING) -- por eso no lo agarró ningún grep de ERROR/CRITICAL
en las verificaciones anteriores del deploy.

Verificado antes de escribir este script (vía SSH, staging_produccion):
sin foreign keys de otras tablas hacia estas dos, sin vistas ni otros
objetos de Postgres dependientes, sin filas huérfanas en
`ir_model`/`ir_model_data` para estos modelos (esa parte de la limpieza
sí funcionó -- `ir.model` en sí siempre existe en el registro, así que su
propio `unlink()` corrió bien; lo único que falló fue el DROP TABLE
dentro de ese unlink porque dependía del modelo BORRADO, no de `ir.model`
mismo). CASCADE por consistencia con el mismo mecanismo nativo de Odoo,
aunque no se encontró ningún dependiente real.
"""

import logging

_logger = logging.getLogger(__name__)

_ORPHANED_TABLES = (
    'l10n_co_payroll_annual_params',
    'l10n_co_payroll_time_params',
)


def migrate(cr, version):
    for table in _ORPHANED_TABLES:
        cr.execute("SELECT to_regclass(%s)", (table,))
        exists = cr.fetchone()[0] is not None
        if not exists:
            _logger.info(
                'Post-migración 18.0.3.0.1: %s ya no existe, nada que hacer.',
                table,
            )
            continue
        cr.execute("SELECT count(*) FROM %s" % table)  # nombre de tabla fijo, no input de usuario
        row_count = cr.fetchone()[0]
        cr.execute("DROP TABLE IF EXISTS %s CASCADE" % table)
        _logger.info(
            'Post-migración 18.0.3.0.1: DROP TABLE %s (tenía %d fila(s), '
            'huérfanas desde 18.0.3.0.0 -- ver docstring de este archivo).',
            table, row_count,
        )
