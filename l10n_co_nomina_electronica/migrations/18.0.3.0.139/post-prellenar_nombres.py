# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """H-024: prellena nombres y apellidos de los empleados existentes.

    Solo los casos no ambiguos (ver dian_utils.split_name); los ambiguos quedan vacíos y el
    sistema exigirá completarlos antes de generar nómina electrónica, PILA o UGPP.
    Los empleados de prueba de habilitación DIAN conservan lo que ya enviaban a la DIAN
    (nombre, primer apellido y segundo apellido de sus 3 palabras)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Employee = env['hr.employee'].with_context(active_test=False)
    campos = Employee._L10N_CO_CAMPOS_NOMBRE
    for employee in Employee.search([]):
        if any(employee[c] for c in campos.values()):
            continue
        if employee.l10n_co_ne_is_habilitacion_test and len((employee.name or '').split()) == 3:
            nombre, apellido1, apellido2 = employee.name.split()
            valores = {'l10n_co_primer_nombre': nombre,
                       'l10n_co_primer_apellido': apellido1,
                       'l10n_co_segundo_apellido': apellido2}
        else:
            valores = Employee._l10n_co_prellenar_nombre(employee.name)
        if any(valores.values()):
            employee.write(valores)
