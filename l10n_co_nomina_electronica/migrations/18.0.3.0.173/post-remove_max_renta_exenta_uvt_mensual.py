# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Elimina el parametro l10n_co_max_renta_exenta_uvt (240 UVT/mes), reemplazado en .172/.173 por
l10n_co_max_renta_exenta_uvt_anual (790 UVT/anio, Art. 206 num. 10 ET, Ley 2277/2022).

El registro viejo estaba en un bloque noupdate: al actualizar, Odoo no lo borra y quedaria
huerfano (nadie lo lee) y confuso en la configuracion. Se borra por code, junto con sus valores
(cascada). Idempotente: si no existe, no hace nada. El codigo ya no lo referencia.
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

CODE_VIEJO = 'l10n_co_max_renta_exenta_uvt'


def borrar_parametro_viejo(env):
    parametros = env['hr.rule.parameter'].with_context(active_test=False).search(
        [('code', '=', CODE_VIEJO)])
    if parametros:
        _logger.info('Eliminando parametro obsoleto %s (%s registro(s)).',
                     CODE_VIEJO, len(parametros))
        parametros.unlink()
    return len(parametros)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    borrar_parametro_viejo(env)
