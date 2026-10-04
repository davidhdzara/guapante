# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Post-migración 18.0.3.0.3 — DROP TABLE explícito de l10n.co.hr.embargo
(embargo híbrido, doc 16: reemplazado por hr.salary.attachment nativo +
extensión colombiana en models/hr_salary_attachment.py).

Mismo patrón exacto que 18.0.3.0.1 (ver ese post-migrate.py para la causa
raíz completa, verificada en `ir_model.py`): borrar el modelo Python de
`l10n.co.hr.embargo` no dispara el DROP TABLE automático de
`ir.model.unlink()` -> `_drop_table()`, porque para cuando corre
`ir.model._process_end()` la clase ya no existe en el registro y
`self.env.get(model.model)` devuelve None -- el DROP se salta en
silencio (log nivel `runbot`, no ERROR/WARNING).

Verificado antes de escribir este script (SSH, staging_produccion):
- `l10n_co_hr_embargo` tiene 0 filas (tabla vacía, no hubo nunca uso real).
- Sin foreign keys de otras tablas hacia `l10n_co_hr_embargo`.

CASCADE por consistencia con el mecanismo nativo, aunque con 0 filas y sin
FKs no debería haber ningún dependiente real que dispare algo.
"""

import logging

_logger = logging.getLogger(__name__)

_ORPHANED_TABLE = 'l10n_co_hr_embargo'


def migrate(cr, version):
    cr.execute("SELECT to_regclass(%s)", (_ORPHANED_TABLE,))
    exists = cr.fetchone()[0] is not None
    if not exists:
        _logger.info(
            'Post-migración 18.0.3.0.3: %s ya no existe, nada que hacer.',
            _ORPHANED_TABLE,
        )
        return
    cr.execute("SELECT count(*) FROM %s" % _ORPHANED_TABLE)  # nombre de tabla fijo, no input de usuario
    row_count = cr.fetchone()[0]
    cr.execute("DROP TABLE IF EXISTS %s CASCADE" % _ORPHANED_TABLE)
    _logger.info(
        'Post-migración 18.0.3.0.3: DROP TABLE %s (tenía %d fila(s), '
        'huérfana desde que se elimino l10n.co.hr.embargo en favor de '
        'hr.salary.attachment -- doc 16).',
        _ORPHANED_TABLE, row_count,
    )
