# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Frente 4, U5b (doc 57): el formato de pagos UGPP lleva los PAGOS al trabajador (Res. 858 art. 2.1.3), no los aportes ni
los descuentos. Las 9 reglas de seguridad social (aportes del empleado SALUD/PENSION/FSP, que son descuentos y salen
negativos, y los 6 aportes de la empresa, que se pagan a entidades) estaban tipadas 'TP Salarial' y ya no lo están.
El XML deja de asignarles el tipo, pero un valor ya guardado no se borra solo al quitarlo del XML: esta migración lo
limpia, SOLO si sigue siendo el que el módulo había puesto ('tp_salarial'). Una regla que alguien reclasificó a mano en
otro tipo no se toca. Lo mismo para CO_PRIMA_BASE (acumulador interno: la base de la prima no es un pago; producción de
Guapante, módulo .56, la trae como 'tp_prestaciones' y el XML actual ya no la tipa). Idempotente."""

import logging

_logger = logging.getLogger(__name__)

_ACUMULADORES = (('hr_salary_rule_co_prima_base', 'tp_prestaciones'),)

_REGLAS = (
    'hr_salary_rule_co_salud_emp', 'hr_salary_rule_co_pension_emp', 'hr_salary_rule_co_fsp',
    'hr_salary_rule_co_salud_cia', 'hr_salary_rule_co_pension_cia', 'hr_salary_rule_co_arl_cia',
    'hr_salary_rule_co_ccf_cia', 'hr_salary_rule_co_sena_cia', 'hr_salary_rule_co_icbf_cia',
)


def migrate(cr, version):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_salary_rule' "
               "AND column_name = 'l10n_co_ugpp_payment_type'")
    if not cr.fetchone():
        return
    cr.execute(
        """UPDATE hr_salary_rule r SET l10n_co_ugpp_payment_type = NULL
             FROM ir_model_data d
            WHERE d.model = 'hr.salary.rule' AND d.res_id = r.id AND d.module = 'l10n_co_nomina_electronica'
              AND d.name IN %s AND r.l10n_co_ugpp_payment_type = 'tp_salarial'""", (_REGLAS,))
    _logger.info('UGPP: %s regla(s) de aportes/descuentos sin tipo de pago UGPP.', cr.rowcount)
    for nombre, tipo in _ACUMULADORES:
        cr.execute(
            """UPDATE hr_salary_rule r SET l10n_co_ugpp_payment_type = NULL
                 FROM ir_model_data d
                WHERE d.model = 'hr.salary.rule' AND d.res_id = r.id AND d.module = 'l10n_co_nomina_electronica'
                  AND d.name = %s AND r.l10n_co_ugpp_payment_type = %s""", (nombre, tipo))
