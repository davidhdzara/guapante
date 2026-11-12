# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Secuencias de nomina electronica por compania (M1, doc 51): el consecutivo DIAN se autoriza
por NIT, y hasta .174 todas las companias colombianas apuntaban a las MISMAS secuencias (consecutivo
NE, temporal PRE-NOM y ajuste NA, de datos, sin compania).

Para cada compania colombiana que apunta a una secuencia compartida (o que no tiene secuencia de
ajuste propia) se crea la suya CONSERVANDO el siguiente numero:
- una sola compania colombiana: el siguiente numero actual de la secuencia compartida (nunca reiniciar
  ni saltar: protege los consecutivos ya autorizados);
- varias: el de cada una sale de SU historial (mayor consecutivo usado con ese prefijo + 1; sin
  historial, 1). El compartido solo sirve de piso si es la unica con historial.
Idempotente: una compania que ya tiene secuencia propia no se toca. Las secuencias compartidas quedan
como plantillas (nadie las usa).
"""

import logging
import re

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _maximo_usado(env, company, prefijo):
    """Mayor numero usado en los consecutivos de la compania con ese prefijo (0 si ninguno)."""
    slips = env['hr.payslip'].with_context(active_test=False).search([
        ('company_id', '=', company.id),
        ('l10n_co_ne_consecutive', '=like', prefijo + '%')])
    patron = re.compile('^%s(\\d+)$' % re.escape(prefijo))
    numeros = [int(m.group(1)) for m in (
        patron.match(s.l10n_co_ne_consecutive or '') for s in slips) if m]
    return max(numeros) if numeros else 0


def separar_secuencias(env, companias=None):
    """companias: las companias a procesar (por defecto, todas las colombianas)."""
    Company = env['res.company'].with_context(active_test=False)
    colombianas = (companias if companias is not None else Company.search([])).filtered(
        lambda c: c._ne_es_colombia())
    for campo, xmlid in Company._NE_SECUENCIAS:
        plantilla = env.ref(xmlid, raise_if_not_found=False)
        if not plantilla:
            continue
        # companias que aun usan la secuencia compartida (o no tienen la propia de ajuste)
        pendientes = []
        for company in colombianas:
            actual = company[campo] if campo else env['ir.sequence'].search([
                ('code', '=', plantilla.code), ('company_id', '=', company.id)], limit=1)
            if not actual or not actual.company_id:
                pendientes.append((company, actual))
        if not pendientes:
            continue
        compartida = plantilla
        historiales = {c.id: _maximo_usado(env, c, plantilla.prefix or '') for c, _a in pendientes}
        con_historial = [cid for cid, usado in historiales.items() if usado]
        for company, actual in pendientes:
            # La que ya apuntaba a otra secuencia compartida distinta de la plantilla usa esa.
            origen = actual if actual and not actual.company_id else compartida
            siguiente_origen = origen.number_next_actual
            usado = historiales[company.id]
            if len(colombianas) == 1:
                siguiente = siguiente_origen
            elif usado:
                piso = siguiente_origen if len(con_historial) == 1 else 0
                siguiente = max(usado + 1, piso)
            else:
                siguiente = 1
            propia = company._ne_crear_secuencia_propia(origen, siguiente)
            if campo:
                company.sudo()[campo] = propia
            _logger.info('Secuencia %s propia para la compania %s: siguiente numero %s.',
                         origen.code, company.name, siguiente)
    return True


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    separar_secuencias(env)
