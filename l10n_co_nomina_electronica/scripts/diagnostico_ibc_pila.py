# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Script de SOLO LECTURA -- diagnostico del IBC de PILA ya reportado (H-017b). Nunca escribe.

Compara, por recibo confirmado (done/paid), el IBC que el archivo PILA anterior reportaba
(CO_BRUTO, o factor x salario si es integral: todo lo devengado, incluido el auxilio de
transporte y los pagos no salariales) con el IBC que dan las reglas nuevas (parte salarial
+ exceso del 40% de los pactados, techo de 25 SMMLV y piso de 1 SMMLV prorrateado).

LIMITES: se calcula DESDE LAS LINEAS ya guardadas (no recalcula la nomina): la base de
vacaciones/licencias (IBC del mes anterior) y los dias por novedad se aproximan, y el
consolidado por varios recibos del mismo mes NO se evalua aqui (por recibo). Sirve para
medir ORDEN DE MAGNITUD y detectar empleados afectados, no para corregir planillas. Lo
que se presento a la UGPP/operador solo se corrige con una planilla tipo N decidida por
David.

USO (producción solo con orden de David; es solo lectura pero consulta datos reales):

    odoo-bin shell -d <base> --no-http --http-port=<libre> < diagnostico_ibc_pila.py

Variables opcionales: DESDE=2026-01-01 HASTA=2026-12-31 (por date_to del recibo).
En el shell de Odoo.sh NO pase --addons-path. No hace commit.
"""

import os
from datetime import date


def _fecha(nombre, defecto):
    valor = os.environ.get(nombre)
    return date.fromisoformat(valor) if valor else defecto


def _diagnostico(env):
    desde = _fecha('DESDE', date(2000, 1, 1))
    hasta = _fecha('HASTA', date(2100, 1, 1))
    slips = env['hr.payslip'].with_context(active_test=False).search([
        ('state', 'in', ('done', 'paid')),
        ('date_to', '>=', desde), ('date_to', '<=', hasta),
        ('employee_id.l10n_co_ne_is_habilitacion_test', '=', False),
        ('line_ids.code', '=', 'CO_BRUTO'),
    ], order='date_to, employee_id')
    filas = []
    for slip in slips:
        contract = slip.contract_id
        lineas = slip.line_ids
        bruto = sum(lineas.filtered(lambda l: l.code == 'CO_BRUTO').mapped('total'))
        factor = slip._rule_parameter('l10n_co_factor_integral_salary', slip.date_from)
        integral = bool(contract.l10n_co_ne_integral_salary)
        anterior = contract.wage * factor if integral else (bruto or contract.wage)

        salarial = sum(l.total for l in lineas if l.salary_rule_id.category_id.code == 'DEV_SAL')
        pactados = sum(
            abs(l.total) for l in lineas
            if l.salary_rule_id.category_id.code == 'DEV_NOSAL'
            and l.salary_rule_id.l10n_co_pila_origen_no_salarial == 'pacto')
        sin_clasificar = [
            l.code for l in lineas
            if l.salary_rule_id.category_id.code == 'DEV_NOSAL' and l.total
            and not l.salary_rule_id.l10n_co_pila_origen_no_salarial]
        remuneracion = contract.wage if integral else salarial
        if integral:
            salarial = contract.wage * factor
        incap = sum(l.total for l in lineas if l.code in (
            'CO_INC_COMUN', 'CO_INC_LABORAL', 'CO_LIC_MAT', 'CO_LIC_PAT'))
        dias = min(slip._ne_dias_bajo_contrato(),
                   slip._rule_parameter('l10n_co_dias_mes_comercial', slip.date_from))
        nuevo = slip._ne_ibc_limites(salarial, incap, remuneracion, pactados, dias)
        filas.append((slip, anterior, nuevo, nuevo - anterior, sin_clasificar))
    return filas


def _imprimir(filas):
    print('Recibos analizados:', len(filas))
    print('%-8s %-34s %-12s %16s %16s %16s' % (
        'Mes', 'Empleado', 'Recibo', 'IBC reportado', 'IBC correcto', 'Diferencia'))
    afectados = 0
    for slip, anterior, nuevo, dif, sin_clasificar in filas:
        if abs(dif) < 1:
            continue
        afectados += 1
        print('%-8s %-34s %-12s %16.0f %16.0f %16.0f%s' % (
            slip.date_to.strftime('%Y-%m'), (slip.employee_id.name or '')[:34],
            (slip.number or str(slip.id))[:12], anterior, nuevo, dif,
            '   SIN CLASIFICAR: %s' % ','.join(sin_clasificar) if sin_clasificar else ''))
    total = sum(f[3] for f in filas)
    print('Recibos con diferencia: %d de %d. Suma de diferencias (IBC): %.0f' % (
        afectados, len(filas), total))
    if not afectados:
        print('Sin diferencias: el IBC reportado coincide con el correcto.')


_imprimir(_diagnostico(env))  # noqa: F821 -- `env` lo inyecta odoo-bin shell
