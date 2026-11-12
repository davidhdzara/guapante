# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Fusion de los datos de varios recibos en UN documento mensual (spike de la etapa 3, doc 53 §5.3).

Funcion PURA (sin Odoo ni base de datos): recibe los diccionarios que ya produce
``HrPayslip._collect_payslip_data()`` por cada recibo del empleado en el mes y devuelve el diccionario
del documento mensual, listo para ``nomina_xml_builder``. No reescribe ningun constructor: la
aritmetica de cada recibo sigue siendo la del motor; aqui solo se AGREGA.

Reglas (cardinalidades del XSD v1.0.6 de la caja de herramientas DIAN, leidas del XSD real):
- ``Devengados/Basico`` [1..1], ``Primas`` [0..1], ``Cesantias`` [0..1], ``Deducciones/Salud`` [1..1],
  ``FondoPension`` [1..1], ``FondoSP`` [0..1] y los escalares [0..1] (Dotacion, RetencionFuente, AFC...):
  se SUMAN los campos numericos.
- ``Transporte`` [0..N]: se suma en UN elemento (el auxilio es mensual: un unico valor por documento).
- Listas [0..N] (HEDs..., Vacaciones, Incapacidades, Licencias, Bonificaciones, Libranzas...): se
  CONCATENAN, cada elemento es un hecho distinto (fechas propias).
- ``Porcentaje`` (Salud, FondoPension, Cesantias, FondoSP): debe ser igual en todos los recibos; si cambia
  dentro del mes se detiene con un error claro (no se promedia en silencio).
- ``FechasPagos`` [1..N]: una fecha por cada fecha de pago distinta (la entrega quien llama, desde paid_date).
- Trabajador, Pago, Empleador: iguales en todos los recibos (si no, error que nombra el campo).
- Totales: suma de los totales de cada recibo; ComprobanteTotal = Devengados - Deducciones.
Dinero con Decimal (sin errores de coma flotante); los valores salen como texto con 2 decimales y los
conteos de dias como enteros, igual que los diccionarios de los recibos.
"""

from decimal import Decimal, ROUND_HALF_UP

CERO = Decimal('0')
DOS = Decimal('0.01')

# Campos numericos: conteos enteros y dinero. Cualquier otro campo numerico no listado se trata como texto
# y debe coincidir (p. ej. Tipo de incapacidad) -- un campo numerico nuevo fallara ruidosamente en las pruebas.
CAMPOS_ENTEROS = {'DiasTrabajados', 'Cantidad'}
CAMPOS_DINERO = {
    'SueldoTrabajado', 'AuxilioTransporte', 'ViaticoManuAlojS', 'ViaticoManuAlojNS', 'Pago', 'PagoNS',
    'PagoIntereses', 'Deduccion', 'DeduccionSP', 'DeduccionSub'}

SECCIONES_IGUALES = ('trabajador', 'pago', 'empleador')
LISTAS_DEVENGADOS = (
    'HEDs', 'HENs', 'HRNs', 'HEDDFs', 'HRDDFs', 'HENDFs', 'HRNDFs', 'Incapacidades', 'Bonificaciones',
    'Auxilios', 'HuelgasLegales', 'OtrosConceptos', 'Compensaciones', 'BonoEPCTVs', 'Comisiones',
    'PagosTerceros', 'Anticipos')
LISTAS_DEDUCCIONES = ('Sindicatos', 'Sanciones', 'Libranzas', 'PagosTerceros', 'Anticipos', 'OtrasDeducciones')
UNICOS_DEVENGADOS = ('Basico', 'Primas', 'Cesantias')
UNICOS_DEDUCCIONES = ('Salud', 'FondoPension', 'FondoSP')
ESCALARES_DEVENGADOS = ('Dotacion', 'ApoyoSost', 'Teletrabajo', 'BonifRetiro', 'Indemnizacion', 'Reintegro')
ESCALARES_DEDUCCIONES = (
    'PensionVoluntaria', 'RetencionFuente', 'AFC', 'Cooperativa', 'EmbargoFiscal', 'PlanComplementarios',
    'Educacion', 'Reintegro', 'Deuda')
GRUPOS_VACACIONES = ('VacacionesComunes', 'VacacionesCompensadas')
GRUPOS_LICENCIAS = ('LicenciaMP', 'LicenciaR', 'LicenciaNR')


class ErrorFusion(ValueError):
    """Los recibos no se pueden fusionar en un solo documento (dato inconsistente)."""


def _dec(valor):
    return Decimal(str(valor if valor not in (None, '') else '0'))


def _dinero(valor):
    return str(_dec(valor).quantize(DOS, rounding=ROUND_HALF_UP))


def _entero(valor):
    return str(int(_dec(valor)))


def _sumar_campo(campo, a, b):
    """a, b: valores (texto/numero) del mismo campo en dos recibos."""
    if campo in CAMPOS_ENTEROS:
        return _entero(_dec(a) + _dec(b))
    if campo in CAMPOS_DINERO:
        return _dinero(_dec(a) + _dec(b))
    # Porcentaje, Tipo y demas: deben coincidir (no se promedia en silencio)
    if str(a) != str(b):
        raise ErrorFusion(
            "El campo '%s' cambia entre recibos del mismo mes (%s frente a %s): no se promedia." % (
                campo, a, b))
    return a


def _sumar_nodo(nombre, acumulado, nuevo):
    """Suma dos nodos unicos {campo: valor}; ``acumulado`` puede ser None."""
    if not nuevo:
        return acumulado
    if acumulado is None:
        return dict(nuevo)
    resultado = dict(acumulado)
    for campo, valor in nuevo.items():
        if campo not in resultado or resultado[campo] in (None, ''):
            resultado[campo] = valor
        elif valor in (None, ''):
            continue
        elif isinstance(valor, (list, dict)):
            raise ErrorFusion("El nodo '%s' trae '%s' estructurado: no se fusiona." % (nombre, campo))
        else:
            resultado[campo] = _sumar_campo(campo, resultado[campo], valor)
    return resultado


def _sumar_escalar(acumulado, nuevo):
    if nuevo is None:
        return acumulado
    if acumulado is None:
        return nuevo
    return _dinero(_dec(acumulado) + _dec(nuevo))


def _fusionar_transporte(recibos):
    """Un unico elemento de transporte con las sumas; sin transporte -> lista vacia."""
    total = {}
    hay = False
    for datos in recibos:
        transporte = datos.get('devengados', {}).get('Transporte')
        if not transporte:
            continue
        if isinstance(transporte, dict):
            transporte = [transporte]
        for item in transporte:
            hay = True
            for campo in ('AuxilioTransporte', 'ViaticoManuAlojS', 'ViaticoManuAlojNS'):
                if item.get(campo) is not None:
                    total[campo] = _sumar_escalar(total.get(campo), item[campo])
    return [total] if hay and total else []


def _fusionar_grupos(recibos, seccion, nombre, grupos):
    """Vacaciones / Licencias: dict de listas -> concatena cada grupo."""
    resultado = {grupo: [] for grupo in grupos}
    hay = False
    for datos in recibos:
        nodo = datos.get(seccion, {}).get(nombre) or {}
        for grupo in grupos:
            items = nodo.get(grupo) or []
            if items:
                hay = True
                resultado[grupo].extend(dict(i) for i in items)
    return resultado if hay else None


def fusionar_devengados(recibos):
    salida = {}
    for nombre in UNICOS_DEVENGADOS:
        acum = None
        for datos in recibos:
            acum = _sumar_nodo(nombre, acum, datos.get('devengados', {}).get(nombre))
        if acum is not None:
            salida[nombre] = acum
    transporte = _fusionar_transporte(recibos)
    if transporte:
        salida['Transporte'] = transporte
    for nombre in LISTAS_DEVENGADOS:
        items = [dict(i) for d in recibos for i in (d.get('devengados', {}).get(nombre) or [])]
        if items:
            salida[nombre] = items
    vacaciones = _fusionar_grupos(recibos, 'devengados', 'Vacaciones', GRUPOS_VACACIONES)
    if vacaciones:
        salida['Vacaciones'] = vacaciones
    licencias = _fusionar_grupos(recibos, 'devengados', 'Licencias', GRUPOS_LICENCIAS)
    if licencias:
        salida['Licencias'] = licencias
    for nombre in ESCALARES_DEVENGADOS:
        acum = None
        for datos in recibos:
            acum = _sumar_escalar(acum, datos.get('devengados', {}).get(nombre))
        if acum is not None:
            salida[nombre] = acum
    return salida


def fusionar_deducciones(recibos):
    salida = {}
    for nombre in UNICOS_DEDUCCIONES:
        acum = None
        for datos in recibos:
            acum = _sumar_nodo(nombre, acum, datos.get('deducciones', {}).get(nombre))
        if acum is not None:
            salida[nombre] = acum
    for nombre in LISTAS_DEDUCCIONES:
        items = [dict(i) for d in recibos for i in (d.get('deducciones', {}).get(nombre) or [])]
        if items:
            salida[nombre] = items
    for nombre in ESCALARES_DEDUCCIONES:
        acum = None
        for datos in recibos:
            acum = _sumar_escalar(acum, datos.get('deducciones', {}).get(nombre))
        if acum is not None:
            salida[nombre] = acum
    return salida


def fusionar_documento(recibos, fechas_pagos, periodo, periodo_nomina='5'):
    """Devuelve el diccionario del documento mensual.

    :param recibos: lista de diccionarios de ``_collect_payslip_data()``, del MISMO empleado y mes.
    :param fechas_pagos: fechas de pago DISTINTAS ('AAAA-MM-DD'), una por pago (de paid_date).
    :param periodo: dict ``Periodo`` del documento (FechaIngreso, FechaLiquidacionInicio/Fin,
        TiempoLaborado, FechaRetiro?, FechaGen) -- lo decide quien llama (D3).
    :param periodo_nomina: codigo del catalogo 5.5.1 ('5' = Mensual).
    """
    if not recibos:
        raise ErrorFusion('No hay recibos que fusionar.')
    if not fechas_pagos:
        raise ErrorFusion('Falta la fecha de pago: FechasPagos exige al menos una (1..N).')
    base = recibos[0]
    for seccion in SECCIONES_IGUALES:
        for otro in recibos[1:]:
            if otro.get(seccion) != base.get(seccion):
                raise ErrorFusion(
                    "La seccion '%s' difiere entre los recibos del mes: el documento mensual la exige "
                    "unica." % seccion)
    documento = {clave: valor for clave, valor in base.items()
                 if clave in ('numero_secuencia', 'lugar_generacion', 'proveedor_xml', 'empleador',
                              'trabajador', 'pago', 'codigo_qr', 'notas')}
    informacion = dict(base.get('informacion_general', {}))
    informacion['PeriodoNomina'] = periodo_nomina
    documento['informacion_general'] = informacion
    documento['periodo'] = dict(periodo)
    documento['fechas_pagos'] = sorted(set(str(f) for f in fechas_pagos))
    documento['devengados'] = fusionar_devengados(recibos)
    documento['deducciones'] = fusionar_deducciones(recibos)
    devengados = sum((_dec(d.get('devengados_total', 0)) for d in recibos), CERO)
    deducciones = sum((_dec(d.get('deducciones_total', 0)) for d in recibos), CERO)
    documento['devengados_total'] = float(devengados)
    documento['deducciones_total'] = float(deducciones)
    documento['comprobante_total'] = float(devengados - deducciones)
    documento['totales'] = {
        'DevengadosTotal': _dinero(devengados), 'DeduccionesTotal': _dinero(deducciones),
        'ComprobanteTotal': _dinero(devengados - deducciones)}
    return documento
