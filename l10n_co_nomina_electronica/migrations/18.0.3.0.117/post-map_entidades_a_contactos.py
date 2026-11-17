# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Codigos PILA (Char) de EPS/AFP/CCF/ARL -> contacto (Many2one).

Mapeo exacto por codigo: si existe UN contacto del tipo correspondiente con
ese codigo PILA, se asigna. Sin coincidencia no se inventa nada (principio
de no usar valores por defecto silenciosos): el campo queda vacio y el
asistente PILA avisa por empleado. En las bases conocidas (staging y
produccion de Guapante) no hay ningun codigo cargado, asi que no mueve filas.
"""
import logging

_logger = logging.getLogger(__name__)

# (tabla, columna_legada, columna_nueva, tipo de entidad)
_MAPEOS = [
    ('hr_employee', 'l10n_co_pila_eps_code', 'l10n_co_pila_eps_id', 'eps'),
    ('hr_employee', 'l10n_co_pila_afp_code', 'l10n_co_pila_afp_id', 'afp'),
    ('hr_employee', 'l10n_co_pila_ccf_code', 'l10n_co_pila_ccf_id', 'ccf'),
    ('res_company', 'l10n_co_pila_arl_code', 'l10n_co_pila_arl_id', 'arl'),
]


def _existe_columna(cr, tabla, columna):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s", (tabla, columna))
    return bool(cr.fetchone())


def migrate(cr, version):
    for tabla, legada, nueva, tipo in _MAPEOS:
        if not (_existe_columna(cr, tabla, legada)
                and _existe_columna(cr, tabla, nueva)):
            continue
        cr.execute(
            """
            UPDATE {tabla} t SET {nueva} = p.id
              FROM (
                    SELECT l10n_co_pila_entity_code AS code, MIN(id) AS id
                      FROM res_partner
                     WHERE l10n_co_entity_type = %s
                       AND l10n_co_pila_entity_code IS NOT NULL
                     GROUP BY l10n_co_pila_entity_code
                    HAVING COUNT(*) = 1
                   ) p
             WHERE t.{nueva} IS NULL AND t.{legada} = p.code
            """.format(tabla=tabla, nueva=nueva, legada=legada), (tipo,))
        _logger.info('%s.%s -> %s: %s filas mapeadas',
                     tabla, legada, nueva, cr.rowcount)
        cr.execute(
            "SELECT COUNT(*) FROM {t} WHERE {l} IS NOT NULL AND {l} <> '' "
            "AND {n} IS NULL".format(t=tabla, l=legada, n=nueva))
        sin_mapa = cr.fetchone()[0]
        if sin_mapa:
            _logger.warning(
                '%s.%s: %s registros con codigo sin contacto coincidente; '
                'quedan vacios y deben completarse a mano.',
                tabla, legada, sin_mapa)
