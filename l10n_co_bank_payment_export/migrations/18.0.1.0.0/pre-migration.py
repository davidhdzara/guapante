"""
Migracion 18.0.1.0.0
Script de pre-migracion: se ejecuta antes de que Odoo cargue el modulo.
En la version inicial no hay nada que migrar.
Este archivo existe como plantilla para versiones futuras.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Instalacion inicial — nada que migrar
        return
    _logger.info(
        'l10n_co_bank_payment_export: pre-migracion desde version %s', version
    )
