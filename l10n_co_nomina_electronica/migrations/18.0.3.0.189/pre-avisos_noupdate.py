# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Avisos del panel (.189): el bloque de datos paso a noupdate="0" en .185, pero una actualizacion solo
sobrescribe un registro si el bloque del XML es noupdate="0" Y el registro NO esta marcado noupdate en la BD.
El aviso de retencion se creo en .180 bajo noupdate="1" y quedo marcado en la BD (verificado en staging: flag
true y codigo de evaluacion viejo); el de parametros ya estaba liberado. Se libera ANTES de cargar los datos
para que el -u los actualice. Idempotente."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_model_data SET noupdate = false
        WHERE module = 'l10n_co_nomina_electronica'
          AND model = 'hr.payroll.dashboard.warning'
          AND noupdate = true
    """)
    _logger.info('Avisos del panel: %s registro(s) liberados de noupdate.', cr.rowcount)
