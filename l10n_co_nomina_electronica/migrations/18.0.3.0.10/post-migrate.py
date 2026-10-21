# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Post-migración 18.0.3.0.10 -- doc 22: paridad visual/estructural con
Facturación Electrónica (CO). Migra los campos planos
l10n_co_ne_software_id/_software_pin/_test_set_id (eliminados de
res.company) a filas de l10n.co.ne.operation_mode, y activa
l10n_co_ne_certification_process (campo nuevo, stored) para compañías
que ya tenían un TestSetID configurado -- para no dejarlas bloqueadas
por el guard nuevo que agrega este mismo ciclo a action_send_test_set()
(hr_payslip.py) sin que nadie note que hay que marcar la casilla nueva.

Los 3 campos planos viejos NO se dropean explícitamente de la tabla
res_company -- a diferencia de 18.0.3.0.1/18.0.3.0.3 (que sí hacían DROP
TABLE porque el modelo ENTERO desaparecía), acá solo desaparecen 3
columnas de un modelo (res.company) que sigue existiendo con muchas
otras columnas -- Odoo tolera columnas huérfanas sin problema, dropearlas
a mano no da ningún beneficio real y sí un riesgo de escribir mal la
migración de una compañía con datos reales cargados.

Verificado contra staging_produccion antes de escribir este script:
1 compañía (Guapante), l10n_co_ne_software_id='TEST-SOFTWARE-ID',
l10n_co_ne_software_pin='TEST-PIN', l10n_co_ne_test_set_id=NULL,
l10n_co_ne_environment='2' (Habilitación).

Hallazgo aparte, no corregido por este script (fuera de alcance, dato
preexistente): esa combinación (environment=Habilitación + software
configurado + TestSetID vacío) ya violaba el @api.constrains
_check_test_set_id ANTES de este ciclo también -- solo que un
@api.constrains no se re-valida contra datos ya guardados, así que nunca
se disparó. Después de esta migración, si alguien abre Ajustes > Nómina
y guarda sin tocar nada, el write disparará la validación y pedirá el
TestSetID -- comportamiento correcto, pero puede sorprender si no se
avisa. Reportado a Tech Lead junto con este script, no es un bug nuevo
de esta migración.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT id, name, l10n_co_ne_software_id, l10n_co_ne_software_pin,
               l10n_co_ne_test_set_id
        FROM res_company
        WHERE l10n_co_ne_software_id IS NOT NULL
          AND l10n_co_ne_software_id != ''
    """)
    companies = cr.fetchall()

    for company_id, company_name, software_id, software_pin, test_set_id in companies:
        cr.execute("""
            INSERT INTO l10n_co_ne_operation_mode
                (software_id, software_pin, test_set_id, company_id,
                 create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, %s, 1, now(), 1, now())
        """, (software_id, software_pin, test_set_id, company_id))
        _logger.info(
            'Post-migración 18.0.3.0.10: creado l10n.co.ne.operation_mode '
            'para la compañía %s (id %s) con el software_id/pin ya '
            'configurado.',
            company_name, company_id,
        )

    cr.execute("""
        UPDATE res_company
        SET l10n_co_ne_certification_process = TRUE
        WHERE l10n_co_ne_test_set_id IS NOT NULL
          AND l10n_co_ne_test_set_id != ''
    """)
    if cr.rowcount:
        _logger.info(
            'Post-migración 18.0.3.0.10: activado l10n_co_ne_certification_process '
            'para %d compañía(s) que ya tenían un TestSetID configurado '
            '(el guard nuevo de action_send_test_set() no las bloquea).',
            cr.rowcount,
        )
    else:
        _logger.info(
            'Post-migración 18.0.3.0.10: ninguna compañía tenía TestSetID '
            'configurado -- l10n_co_ne_certification_process queda en '
            'False (default) para todas, tal como se esperaba.',
        )
