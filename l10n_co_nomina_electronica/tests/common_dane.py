# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Direcciones de prueba con códigos DANE (H-F3-06): el XML de una dirección colombiana ya no cae al código postal ni al código alfabético del departamento."""

from odoo.addons.l10n_co_nomina_electronica.services import dian_utils

SIN_ASIGNAR = 89          # número que el DANE no usa para ningún departamento


def ciudad_con_dane(env, estado, nombre):
    """Ciudad de prueba con un código DANE del departamento ``estado`` (al departamento sin código numérico se le pone uno)."""
    codigo = dian_utils.get_department_code(estado)
    if not (codigo.isdigit() and len(codigo) == 2):
        codigo = str(SIN_ASIGNAR)
        if 'l10n_co_edi_code' in estado._fields:
            estado.l10n_co_edi_code = SIN_ASIGNAR
        else:
            estado.code = codigo
    return env['res.city'].create({'name': nombre, 'state_id': estado.id, 'country_id': estado.country_id.id, 'l10n_co_edi_code': int(codigo + '999')})
