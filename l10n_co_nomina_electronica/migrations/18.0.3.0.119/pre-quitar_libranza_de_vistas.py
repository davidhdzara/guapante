# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Quita hr.contract.l10n_co_ne_libranza de las vistas ya guardadas.

El campo se retira en .119. hr_contract_views.xml carga antes que
hr_contract_deductions_views.xml: al validar el arbol de herencia de
hr.contract, Odoo toparia con la copia guardada (version anterior) de la vista
hija que todavia nombra el campo y el -u fallaria con "Field
l10n_co_ne_libranza does not exist". Se limpia el arch guardado ANTES de que
el modulo recargue sus vistas; la vista se vuelve a escribir desde el XML.
"""
import logging
import re

from psycopg2.extras import Json

_logger = logging.getLogger(__name__)

_CAMPO = re.compile(r'[ \t]*<field\s+name="l10n_co_ne_libranza"[^>]*/>[ \t]*\n?')


def migrate(cr, version):
    cr.execute(
        "SELECT id, arch_db FROM ir_ui_view "
        "WHERE arch_db::text LIKE %s", ('%l10n_co_ne_libranza%',))
    for view_id, arch in cr.fetchall():
        if isinstance(arch, dict):  # jsonb traducible: una cadena por idioma
            nuevo = {k: _CAMPO.sub('', v) if isinstance(v, str) else v
                     for k, v in arch.items()}
            cr.execute("UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                       (Json(nuevo), view_id))
        else:
            cr.execute("UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                       (_CAMPO.sub('', arch), view_id))
        _logger.info('Vista %s: referencia a l10n_co_ne_libranza retirada.',
                     view_id)
