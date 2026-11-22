# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Ayuda de pruebas (no es una prueba): un recibo CONFIRMADO de un mes anterior con SOLO las lineas que lee ``HrPayslip._ne_ibc_mes_anterior`` (H-F1-11): la base CO_SS_BASE_IBC y los dias
de salud y pension CO_DIAS_SP. Sin ellas no hace falta calcular un recibo completo para fijar la base del mes anterior; el recibo no tiene ausencias, asi que la suspension y la incapacidad
de ese mes valen 0."""


def crear_recibo_previo(env, empleado, contrato, estructura, desde, hasta, base, dias=30.0):
    recibo = env['hr.payslip'].create({
        'name': 'Recibo previo %s' % desde, 'employee_id': empleado.id, 'contract_id': contrato.id, 'company_id': contrato.company_id.id,
        'struct_id': estructura.id, 'date_from': desde, 'date_to': hasta})
    for codigo, total in (('CO_SS_BASE_IBC', base), ('CO_DIAS_SP', dias)):
        regla = env['hr.salary.rule'].search([('code', '=', codigo), ('struct_id', '=', estructura.id)], limit=1)
        assert regla, 'La estructura %s no tiene la regla %s' % (estructura.name, codigo)
        env['hr.payslip.line'].create({
            'slip_id': recibo.id, 'salary_rule_id': regla.id, 'code': codigo, 'name': codigo, 'contract_id': contrato.id, 'employee_id': empleado.id,
            'quantity': 1.0, 'rate': 100.0, 'amount': total, 'total': total})
    recibo.state = 'done'
    return recibo
