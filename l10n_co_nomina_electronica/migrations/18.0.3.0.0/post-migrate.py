# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Post-migración 18.0.3.0.0 — Migración de annual_params/time_params a
hr.rule.parameter nativo (doc 12/13).

Qué NO hace falta migrar manualmente (verificado contra el código fuente
real de Odoo, `odoo/addons/base/models/ir_model.py`, en el servidor de
Guapante -- mismo criterio de verificación que exigió Tech Lead):

- Las tablas `l10n_co_payroll_annual_params` y `l10n_co_payroll_time_params`
  y la columna huérfana `l10n_co_retefuente_uvt.annual_params_id`: al quitar
  los modelos Python, el mecanismo estándar de limpieza de `-u`
  (`ir.model._process_end` + `ir.model.unlink()` -> `_drop_table()`, que usa
  `DROP TABLE ... CASCADE`) los elimina automáticamente durante la
  actualización del módulo. No es necesario ni deseable duplicar esa lógica
  aquí a mano.
- Los ~34 nuevos `hr.rule.parameter`/`hr.rule.parameter.value` (data file
  `l10n_co_rule_parameters_data.xml`): son registros nuevos con external ID
  nuevo, sin fila manual preexistente con la que puedan chocar (a diferencia
  del bug real que encontramos en la migración 18.0.2.1.0) -- no requieren
  pre-migrate de vinculación.

Qué SÍ hace esta migración: `l10n.co.retefuente.uvt.uvt_value` deja de ser
`related='annual_params_id.uvt'` y pasa a `compute='_compute_uvt_value',
store=True` con el mismo valor legal (viene del mismo parámetro UVT,
solo cambia el modelo de origen). El valor ya almacenado debería seguir
siendo numéricamente correcto, pero se fuerza el recálculo explícito aquí
en vez de confiar en que Odoo detecte el cambio de related->compute y
recalcule solo -- mismo criterio de "no dar nada por sentado sin
verificarlo" que exigió Tech Lead para el bug de tipos de esta semana.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT r.id
        FROM l10n_co_retefuente_uvt r
        JOIN ir_model ON ir_model.model = 'l10n.co.retefuente.uvt'
    """)
    ids = [row[0] for row in cr.fetchall()]
    if not ids:
        _logger.info(
            'Post-migración 18.0.3.0.0: no hay registros de '
            'l10n.co.retefuente.uvt para recalcular.'
        )
        return

    env = None
    try:
        from odoo import api, SUPERUSER_ID
        env = api.Environment(cr, SUPERUSER_ID, {})
    except ImportError:  # pragma: no cover - Odoo siempre expone odoo.api
        pass

    if env is None:
        _logger.warning(
            'Post-migración 18.0.3.0.0: no se pudo obtener el entorno ORM, '
            'se omite el recálculo explícito de uvt_value (%d registro(s)). '
            'El valor almacenado previamente ya era numéricamente correcto '
            '(mismo dato legal, related->compute), pero conviene forzar el '
            'recálculo manualmente vía ORM si esto ocurre.',
            len(ids),
        )
        return

    records = env['l10n.co.retefuente.uvt'].browse(ids)
    records._compute_uvt_value()
    records.flush_recordset(['uvt_value'])

    _logger.info(
        'Post-migración 18.0.3.0.0: uvt_value recalculado desde '
        'hr.rule.parameter (código l10n_co_uvt) para %d registro(s) de '
        'l10n.co.retefuente.uvt.',
        len(ids),
    )
