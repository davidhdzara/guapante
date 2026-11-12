# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Script de UN SOLO USO -- NO se ejecuta solo (no vive en migrations/ a propósito).

Recalcula los campos nativos almacenados net_wage / gross_wage (y basic_wage) de los payslips
que ya existen, tras el arreglo de hr.payslip._compute_basic_net (.107): net_wage = línea
CO_NETO (o CO_PRIMA_NETO / CO_LIQ_NETO / CO_BON_NETO) y gross_wage = línea CO_BRUTO. Son campos
calculados almacenados: no se actualizan solos para recibos ya generados.

NO toca líneas, asientos contables ni el XML DIAN (esos usan CO_NETO directo). Tampoco cambia
el estado de ningún recibo. No corrige PDFs ni archivos de banco ya generados con el valor viejo.

USO (solo con autorización puntual de David sobre el ambiente; NO en producción sin su orden):

    # 1) Simulación (por defecto): lista los recibos cuyo net_wage/gross_wage cambiaría.
    odoo-bin shell -d <base> --no-http --http-port=<libre> < recomputar_net_wage_gross_wage.py

    # 2) Aplicar (revise primero la simulación y tenga un respaldo):
    APLICAR=1 odoo-bin shell -d <base> --no-http --http-port=<libre> < recomputar_net_wage_gross_wage.py

En el shell de Odoo.sh NO pase --addons-path (data_dir real: /home/odoo/data).
El script hace commit solo con APLICAR=1.
"""

import os

_NETO = ('CO_NETO', 'CO_PRIMA_NETO', 'CO_LIQ_NETO', 'CO_BON_NETO')
_BRUTO = ('CO_BRUTO',)


def _recomputar(env, aplicar):
    Payslip = env['hr.payslip'].with_context(active_test=False)
    candidatos = Payslip.search([('line_ids.code', 'in', list(_NETO) + list(_BRUTO))])
    cambian = []
    for p in candidatos:
        neto = sum(p.line_ids.filtered(lambda l: l.code in _NETO).mapped('total'))
        bruto = sum(p.line_ids.filtered(lambda l: l.code in _BRUTO).mapped('total'))
        tiene_neto = bool(p.line_ids.filtered(lambda l: l.code in _NETO))
        tiene_bruto = bool(p.line_ids.filtered(lambda l: l.code in _BRUTO))
        if (tiene_neto and abs(p.net_wage - neto) > 0.005) or (
                tiene_bruto and abs(p.gross_wage - bruto) > 0.005):
            cambian.append(p)
            print('  payslip id=%s | %s | estado=%s | net_wage %s -> %s | gross_wage %s -> %s' % (
                p.id, p.name, p.state, p.net_wage, neto if tiene_neto else p.net_wage,
                p.gross_wage, bruto if tiene_bruto else p.gross_wage))
    print('Recibos con CO_NETO/CO_BRUTO: %d | cuyo net/gross almacenado cambiaría: %d' % (
        len(candidatos), len(cambian)))
    if aplicar and cambian:
        registros = Payslip.browse([p.id for p in cambian])
        for nombre in ('basic_wage', 'gross_wage', 'net_wage'):
            env.add_to_compute(Payslip._fields[nombre], registros)
        env.flush_all()  # ejecuta los computes pendientes y escribe
        env.cr.commit()
        print('APLICADO y confirmado (commit) sobre %d recibos.' % len(cambian))
    else:
        print('SIMULACIÓN: no se escribió nada. Use APLICAR=1 para aplicar.')


# En "odoo-bin shell" la variable ``env`` ya existe.
_recomputar(env, aplicar=os.environ.get('APLICAR') == '1')  # noqa: F821
