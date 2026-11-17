# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Frente 4, U2 (doc 57): el formulario del aportante UGPP usa las listas de la Guía V-20.1.

1. Naturaleza jurídica: desaparece 'otra' (la Guía no la tiene). Tipo de aportante: desaparece 'independiente'.
   Ambos valores quedan en NULL (el reporte pide completar el dato con un error claro: no se asume otro valor).
2. ``l10n_co_ugpp_special_autoretention`` se retira: la columna "Autorretención especial" del formato UGPP es la
   exoneración del art. 114-1 ET (``l10n_co_ne_exoneration_1607``), una sola fuente. Si una compañía tenía el campo
   retirado en True y la exoneración en False, SOLO se avisa en el log; no se tocan datos. La columna del campo
   retirado no se borra (queda sin uso).
Idempotente. Producción de Guapante (leída 2026-11-14): ambos campos en NULL, sin conflicto."""

import logging

_logger = logging.getLogger(__name__)


def _existe(cr, tabla, columna):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
               (tabla, columna))
    return bool(cr.fetchone())


def migrate(cr, version):
    if _existe(cr, 'res_company', 'l10n_co_ugpp_legal_nature'):
        cr.execute("UPDATE res_company SET l10n_co_ugpp_legal_nature = NULL WHERE l10n_co_ugpp_legal_nature = 'otra'")
        if cr.rowcount:
            _logger.warning('UGPP: %s compañía(s) con naturaleza jurídica "otra" (ya no existe): quedó vacía, '
                            'complétela en Ajustes.', cr.rowcount)
    if _existe(cr, 'res_company', 'l10n_co_ugpp_contributor_type'):
        cr.execute("UPDATE res_company SET l10n_co_ugpp_contributor_type = NULL "
                   "WHERE l10n_co_ugpp_contributor_type = 'independiente'")
        if cr.rowcount:
            _logger.warning('UGPP: %s compañía(s) con tipo de aportante "independiente" (ya no existe): quedó vacío, '
                            'complételo en Ajustes.', cr.rowcount)
    if _existe(cr, 'res_company', 'l10n_co_ugpp_special_autoretention') \
            and _existe(cr, 'res_company', 'l10n_co_ne_exoneration_1607'):
        cr.execute("SELECT id, name FROM res_company WHERE l10n_co_ugpp_special_autoretention IS TRUE "
                   "AND l10n_co_ne_exoneration_1607 IS NOT TRUE")
        for id_, nombre in cr.fetchall():
            _logger.warning('UGPP: la compañía %s (id %s) tenía "Autorretención especial" marcada y la exoneración '
                            'del art. 114-1 ET sin marcar. El formato UGPP ahora usa la exoneración: revise si '
                            'corresponde marcarla (no se cambió ningún dato).', nombre, id_)
