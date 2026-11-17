# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Post-migración (.114): mapea el texto viejo de hr.contract.l10n_co_pila_actividad_economica
(guardado en ..._legacy) a una fila del catálogo l10n.co.pila.ciiu.

Criterio conservador: SOLO coincidencia EXACTA del código (sin espacios) con una actividad
vigente del catálogo. Lo que no coincide NO se adivina: queda en blanco y se registra en el log
(contrato, empleado y texto) para que RRHH lo vuelva a elegir. La columna legacy se conserva
como respaldo; no se borra. No toca la Clase de Riesgo del contrato (no la pisa).
Idempotente: solo rellena contratos con la actividad vacía.
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_LEGACY = 'l10n_co_pila_actividad_economica_legacy'


def migrate(cr, version):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_contract' AND column_name = %s",
        (_LEGACY,))
    if not cr.fetchone():
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        'SELECT id, %s FROM hr_contract WHERE %s IS NOT NULL AND TRIM(%s) <> \'\' '
        'AND l10n_co_pila_actividad_economica IS NULL' % (_LEGACY, _LEGACY, _LEGACY))
    pendientes = cr.fetchall()
    if not pendientes:
        return
    Catalogo = env['l10n.co.pila.ciiu']
    mapeados = sin_mapear = 0
    for contrato_id, texto in pendientes:
        codigo = (texto or '').strip()
        actividad = Catalogo.search([('code', '=', codigo)], order='date_start desc', limit=1)
        if actividad:
            env['hr.contract'].browse(contrato_id).write({'l10n_co_pila_actividad_economica': actividad.id})
            mapeados += 1
        else:
            sin_mapear += 1
            _logger.warning(
                'Contrato id=%s: actividad económica "%s" sin coincidencia exacta en el catálogo; '
                'queda en blanco (valor viejo en %s).', contrato_id, texto, _LEGACY)
    _logger.info('Actividad económica ARL: %s contratos mapeados, %s sin mapear.', mapeados, sin_mapear)
