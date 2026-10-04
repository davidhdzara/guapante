# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Contenido emulado del set de pruebas de habilitación DIAN (doc 39).

Separa, para el wizard de habilitación (doc 34), 2 fuentes de dato
distintas:

- El dato REAL de la empresa (razón social, NIT+DV, dirección, DANE) se
  sigue leyendo en caliente de ``company``/``company.partner_id`` --
  eso ya lo hace ``hr_payslip._collect_payslip_data()`` vía
  ``services/dian_utils.py`` (``compute_dv``, ``get_department_code``,
  ``get_city_code``), sin tocar nada aquí.
- El contenido del "empleado de prueba" (este archivo) es 100%
  hardcodeado, igual en cualquier instalación -- nunca depende de un
  ``hr.employee``/``hr.contract``/``hr.payslip`` real de producción.
  Calca el patrón ``RECEIVER``/``TEST_LINE_ITEM``/``DOC_TOTALS`` de
  ``insotech_dian_wizard`` (Facturación, Odoo 19), adaptado a Nómina.

La DIAN exige únicamente "cuatro (4) Nóminas Electrónicas y cuatro (4)
Notas de Ajuste como documentos MÍNIMOS REQUERIDOS ACEPTADOS" (Guía
oficial "Registro y Selección del Modo de Operación - Nómina
Electrónica", confirmado por Tech Lead 2026-10-04 contra el ZIP oficial
de la Caja de Herramientas) -- no exige diversidad de empleados ni de
periodos. El salario/wage es intencionalmente un valor fijo simple: no
aplica el principio "cero hardcoded" del doc 10 porque no es un valor
normativo (SMMLV, UVT, etc.) sino contenido de prueba inventado.
"""

TEST_EMPLOYEES = [
    {
        'name': 'EMPLEADO PRUEBA UNO',
        'identification_id': '1000000001',
    },
    {
        'name': 'EMPLEADO PRUEBA DOS',
        'identification_id': '1000000002',
    },
    {
        'name': 'EMPLEADO PRUEBA TRES',
        'identification_id': '1000000003',
    },
    {
        'name': 'EMPLEADO PRUEBA CUATRO',
        'identification_id': '1000000004',
    },
]

# Campos compartidos por los 4 empleados de prueba -- ningún dato bancario
# real, método de pago "Efectivo" para no requerir banco/cuenta.
TEST_EMPLOYEE_COMMON_VALUES = {
    'l10n_co_ne_document_type': '13',  # Cédula de Ciudadanía
    'l10n_co_ne_worker_type': '01',  # Trabajador Dependiente
    'l10n_co_ne_worker_subtype': '00',  # No Aplica
    'l10n_co_ne_high_risk_pension': False,
    'l10n_co_ne_payment_method': '10',  # Efectivo -- sin banco/cuenta
    'l10n_co_ne_is_habilitacion_test': True,
}

# Contrato de prueba: salario fijo simple, a término indefinido,
# iniciado con suficiente antigüedad para que el cálculo de tiempo
# laborado y prestaciones no produzca casos borde.
TEST_CONTRACT_WAGE = 1800000.0
TEST_CONTRACT_START_YEARS_AGO = 2
TEST_CONTRACT_COMMON_VALUES = {
    'l10n_co_ne_contract_type': '2',  # Término Indefinido
    'l10n_co_ne_integral_salary': False,
    'wage': TEST_CONTRACT_WAGE,
    'state': 'open',
}
