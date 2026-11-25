# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Huella del cálculo de un recibo de nómina (C-24, doc 106 §13). Python puro (sin Odoo): resume los datos PROPIOS del recibo con los que se calculó la hoja para comparar, al confirmar, si
siguen siendo los mismos. Quien la usa es ``hr.payslip`` (``_ne_huella_calculo``): aquí solo se normaliza y se resume.

Normalización: las listas se ordenan por su texto (el orden de las líneas no cambia la huella, pero las repetidas SÍ cuentan), los números se redondean a 6 decimales y ``-0.0`` vale ``0.0``, las
fechas van en ISO y un vínculo vacío es ``false``. El resultado lleva el prefijo de la versión de la fórmula: cambiar la fórmula cambia la versión y toda huella anterior queda desactualizada."""

import hashlib
import json

VERSION = '2'


def _numero(valor):
    return round(float(valor or 0.0), 6) + 0.0          # + 0.0: -0.0 -> 0.0


def _fecha(valor):
    return valor.isoformat() if valor else False


def _vinculo(valor):
    return valor or False


def _ordenadas(filas):
    return sorted(filas, key=json.dumps)


def huella(cabecera, salario, entradas, dias, ajustes, ausencias, mes=None):
    """Texto ``"<versión>:<sha256>"`` de los datos de un recibo.

    :param cabecera: (empleado_id, contrato_id, estructura_id, fecha_desde, fecha_hasta)
    :param salario: salario del contrato del recibo
    :param entradas: iterable de (tipo_de_novedad_id, importe)
    :param dias: iterable de (tipo_de_entrada_de_trabajo_id, número_de_días, número_de_horas)
    :param ajustes: iterable de (regla_id, cantidad, porcentaje, importe)
    :param ausencias: iterable de (ausencia_id, fecha_desde, fecha_hasta, tipo_de_ausencia_id)
    :param mes: lo que la retención lee del mes (R-2): ``None`` o ``[cierra, [[recibo_id, base, base_salarial, salud, pensión, retenido, exento], ...]]``
    """
    empleado, contrato, estructura, desde, hasta = cabecera
    datos = {
        'cabecera': [_vinculo(empleado), _vinculo(contrato), _vinculo(estructura), _fecha(desde), _fecha(hasta)],
        'salario': _numero(salario),
        'entradas': _ordenadas([[_vinculo(tipo), _numero(importe)] for tipo, importe in entradas]),
        'dias': _ordenadas([[_vinculo(tipo), _numero(numero), _numero(horas)] for tipo, numero, horas in dias]),
        'ajustes': _ordenadas([[_vinculo(regla), _numero(cantidad), _numero(porcentaje), _numero(importe)] for regla, cantidad, porcentaje, importe in ajustes]),
        'ausencias': _ordenadas([[_vinculo(ausencia), _fecha(inicio), _fecha(fin), _vinculo(tipo)] for ausencia, inicio, fin, tipo in ausencias]),
        'mes': mes,
    }
    texto = json.dumps(datos, sort_keys=True, separators=(',', ':'))
    return '%s:%s' % (VERSION, hashlib.sha256(texto.encode('utf-8')).hexdigest())
