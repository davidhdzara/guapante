# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""H-F1-07 (doc 92; decisión del TL del 22-nov): la compañía elige cómo se paga el dominical con salario mensual (``l10n_co_ne_pago_dominical_mensual``), SIN valor por defecto. Las compañías
colombianas que YA existían quedan en «día ordinario + recargo»: es la decisión D1 de David del 17-nov-2026 (factor total 1,80 / 1,90 / 2,00) y lo que el módulo pagaba hasta .309, así que ningún valor
calculado cambia. No es un valor por defecto silencioso: se deja en el log qué compañías se migraron. Otro cliente elige «solo el recargo» en Ajustes. Idempotente: solo toca las compañías sin elección."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE res_company c SET l10n_co_ne_pago_dominical_mensual = 'dia_mas_recargo'
          FROM res_partner p
          JOIN res_country k ON k.id = p.country_id
         WHERE p.id = c.partner_id AND k.code = 'CO' AND c.l10n_co_ne_pago_dominical_mensual IS NULL
     RETURNING c.id, c.name""")
    filas = cr.fetchall()
    _logger.info('H-F1-07 (.310): %d compañías colombianas quedaron en «día ordinario + recargo» para el pago del dominical con salario mensual (decisión D1 de David, 17-nov-2026; lo que se pagaba hasta .309): %s',
                 len(filas), filas)
