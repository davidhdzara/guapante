# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """SLN: llena ibc_sln y dias_sln de los consolidados existentes desde sus recibos.
    Solo escribe esos dos campos (no toca el IBC ni las planillas ya presentadas)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Consolidado = env['l10n.co.ibc.mensual']
    for cons in Consolidado.search([]):
        valores = Consolidado._valores_sln(cons.payslip_ids, cons.ibc_sp, cons.dias_sp)
        cons.write(valores)
