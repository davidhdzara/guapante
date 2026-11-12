# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# Periodo propio (dias) -> schedule_pay nativo de hr.contract. El periodo de 10 dias (decenal)
# no tiene equivalente nativo: se deja el valor de schedule_pay como esta y se informa.
_EQUIVALENCIA = {'7': 'weekly', '14': 'bi-weekly', '15': 'semi-monthly', '30': 'monthly'}


def migrate(cr, version):
    """Retira l10n_co_payroll_period (ninguna regla lo leia) en favor de schedule_pay nativo.

    Solo traslada los periodos distintos de mensual a contratos cuyo schedule_pay sigue en el
    valor por defecto 'monthly' (o vacio), para no pisar un schedule_pay ya configurado a mano.
    Luego borra la columna huerfana."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_contract' AND column_name = 'l10n_co_payroll_period'""")
    if not cr.fetchone():
        return
    for periodo, schedule in _EQUIVALENCIA.items():
        if schedule == 'monthly':
            continue
        cr.execute("""
            UPDATE hr_contract SET schedule_pay = %s
            WHERE l10n_co_payroll_period = %s AND (schedule_pay IS NULL OR schedule_pay = 'monthly')""",
                   (schedule, periodo))
        _logger.info('l10n_co_payroll_period=%s -> schedule_pay=%s: %s contrato(s)',
                     periodo, schedule, cr.rowcount)
    cr.execute("SELECT count(*) FROM hr_contract WHERE l10n_co_payroll_period = '10'")
    decenal = cr.fetchone()[0]
    if decenal:
        _logger.warning(
            '%s contrato(s) con periodo decenal (10 dias): schedule_pay nativo no tiene '
            'equivalente; revisar a mano.', decenal)
    cr.execute("ALTER TABLE hr_contract DROP COLUMN l10n_co_payroll_period")
