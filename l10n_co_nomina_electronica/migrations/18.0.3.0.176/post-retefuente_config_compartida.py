# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Configuracion de retencion (l10n.co.retefuente.uvt) compartida por pais/anio (M2, doc 51).

Los registros que carga el modulo (2024, 2025, 2026) quedaron atados a la compania con la que se
instalo (default env.company). La UVT y la tabla son de Colombia, no de una compania: pasan a
compartidos (company_id vacio). Una compania que necesite algo distinto crea la suya, que tiene
prioridad. NO se tocan los registros que una compania haya creado: solo los de los datos del modulo
(por xml-id). Idempotente.
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

XMLIDS = (
    'l10n_co_nomina_electronica.l10n_co_retefuente_uvt_2024',
    'l10n_co_nomina_electronica.l10n_co_retefuente_uvt_2025',
    'l10n_co_nomina_electronica.l10n_co_retefuente_uvt_2026',
)


def compartir_registros_del_modulo(env):
    pasados = 0
    for xmlid in XMLIDS:
        registro = env.ref(xmlid, raise_if_not_found=False)
        if registro and registro.company_id:
            registro.company_id = False
            pasados += 1
    if pasados:
        _logger.info('Configuracion de retencion: %s registro(s) del modulo pasan a compartidos.',
                     pasados)
    return pasados


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    compartir_registros_del_modulo(env)
