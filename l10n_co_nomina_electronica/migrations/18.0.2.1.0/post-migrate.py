# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Post-migración 18.0.2.1.0 — Fusión de UVT (adenda 10a, punto 2).

`l10n.co.retefuente.uvt.uvt_value` deja de ser un campo propio editable y
pasa a ser `related='annual_params_id.uvt'`. Esta migración relaciona
cada registro existente de `l10n_co_retefuente_uvt` con su
`l10n_co_payroll_annual_params` correspondiente (mismo year + company_id).

Verificado el 2026-09-02 contra `staging_produccion` de Guapante: los 3
años existentes (2024/2025/2026) coinciden en valor entre ambos modelos
-- no hay conflicto que resolver, es un relink directo. Si en el futuro
un año no coincidiera, el UPDATE de abajo lo relinkea igual (por
year+company, no por valor), y el valor de annual_params pasa a ser la
única fuente de verdad desde ese momento -- por diseño, no se hace
ningún intento de reconciliar valores divergentes en silencio.

Si algún registro de retefuente_uvt no encuentra su annual_params
correspondiente (año sin configurar todavía en annual_params), queda
sin relacionar y su `uvt_value` calculará en 0 hasta que alguien cree
el registro de Parámetros Anuales para ese año -- se loguea para que
sea visible, no se falla la migración completa por un año faltante.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE l10n_co_retefuente_uvt r
        SET annual_params_id = p.id
        FROM l10n_co_payroll_annual_params p
        WHERE p.year = r.year::integer
          AND p.company_id = r.company_id
          AND r.annual_params_id IS NULL
    """)
    _logger.info(
        'Migración UVT (18.0.2.1.0): %d registro(s) de l10n.co.retefuente.uvt '
        'relacionados con su l10n.co.payroll.annual.params.',
        cr.rowcount,
    )

    cr.execute("""
        SELECT r.id, r.year, r.company_id
        FROM l10n_co_retefuente_uvt r
        WHERE r.annual_params_id IS NULL
    """)
    unmatched = cr.fetchall()
    if unmatched:
        _logger.warning(
            'Migración UVT (18.0.2.1.0): %d registro(s) de '
            'l10n.co.retefuente.uvt SIN l10n.co.payroll.annual.params '
            'correspondiente (id, year, company_id): %s. '
            'Su uvt_value quedará en 0 hasta que se cree el registro de '
            'Parámetros Anuales para ese año/compañía.',
            len(unmatched), unmatched,
        )
