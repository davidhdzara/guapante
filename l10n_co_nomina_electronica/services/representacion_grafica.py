# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Datos de la representación gráfica del documento soporte de pago de nómina electrónica (Res. 13 de 2021 art. 24, con
el contenido mínimo de los arts. 5 y 17 y el QR del Anexo §13.1).

Servicio puro (sin Odoo): lee el XML YA validado por la DIAN y devuelve lo que se muestra. La representación es "una
imagen de la información consignada en el XML" (Anexo §13.1): nada se recalcula, para que no pueda diferir del XML."""

from lxml import etree

from .documento_merge import CLAVES_DINERO_DEDUCCIONES, CLAVES_DINERO_DEVENGADOS


class ErrorRepresentacion(Exception):
    """El XML no trae lo que la representación exige."""


def _atributos(nodo, *nombres):
    return {n: (nodo.get(n) if nodo is not None else None) or '' for n in nombres}


def _conceptos(seccion, claves):
    """``[(nodo, atributo, valor)]``: cada atributo en dinero (``claves``) de la sección, tal como viene en el XML."""
    filas = []
    if seccion is None:
        return filas
    for nodo in seccion.iter():
        if not isinstance(nodo.tag, str):
            continue
        for atributo, valor in nodo.attrib.items():
            if atributo in claves and valor not in ('', None):
                filas.append((etree.QName(nodo).localname, atributo, valor))
    return filas


def datos_representacion(xml_bytes):
    """Diccionario con los datos de la representación gráfica a partir del XML validado.

    ``tipo``: 'documento' (art. 5), 'nota_reemplazar' o 'nota_eliminar' (art. 17). Lanza ``ErrorRepresentacion`` si falta
    el CUNE, el número o el QR (sin ellos no hay representación válida)."""
    raiz = etree.fromstring(xml_bytes)
    ns = raiz.nsmap.get(None, '')

    def hallar(etiqueta):
        return raiz.find('.//{%s}%s' % (ns, etiqueta))

    def texto(etiqueta):
        nodo = hallar(etiqueta)
        return (nodo.text or '').strip() if nodo is not None else ''

    reemplazar, eliminar = hallar('Reemplazar'), hallar('Eliminar')
    tipo = 'nota_reemplazar' if reemplazar is not None else 'nota_eliminar' if eliminar is not None else 'documento'
    info = hallar('InformacionGeneral')
    secuencia = hallar('NumeroSecuenciaXML')
    empleador, trabajador, pago = hallar('Empleador'), hallar('Trabajador'), hallar('Pago')
    proveedor = hallar('ProveedorXML')
    cune = (info.get('CUNE') if info is not None else '') or ''
    numero = (secuencia.get('Numero') if secuencia is not None else '') or ''
    qr = texto('CodigoQR')
    faltan = [nombre for nombre, valor in (('CUNE', cune), ('número del documento', numero), ('CodigoQR', qr)) if not valor]
    if faltan:
        raise ErrorRepresentacion('El XML validado no trae: %s.' % ', '.join(faltan))
    predecesor = hallar('ReemplazandoPredecesor') if tipo == 'nota_reemplazar' else hallar('EliminandoPredecesor')
    return {
        'tipo': tipo,
        'cune': cune,
        'numero': numero,
        'fecha_generacion': (info.get('FechaGen') or '') if info is not None else '',
        'hora_generacion': (info.get('HoraGen') or '') if info is not None else '',
        'ambiente': (info.get('Ambiente') or '') if info is not None else '',
        'empleador': _atributos(empleador, 'RazonSocial', 'PrimerApellido', 'SegundoApellido', 'PrimerNombre',
                                'OtrosNombres', 'NIT', 'DV'),
        'trabajador': _atributos(trabajador, 'PrimerApellido', 'SegundoApellido', 'PrimerNombre', 'OtrosNombres',
                                 'NumeroDocumento'),
        'medio_pago': _atributos(pago, 'Forma', 'Metodo'),
        'proveedor': _atributos(proveedor, 'RazonSocial', 'NIT', 'DV', 'SoftwareID'),
        'predecesor': _atributos(predecesor, 'NumeroPred', 'CUNEPred', 'FechaGenPred'),
        'devengados': _conceptos(hallar('Devengados'), CLAVES_DINERO_DEVENGADOS),
        'deducciones': _conceptos(hallar('Deducciones'), CLAVES_DINERO_DEDUCCIONES),
        'devengados_total': texto('DevengadosTotal'),
        'deducciones_total': texto('DeduccionesTotal'),
        'comprobante_total': texto('ComprobanteTotal'),
        # El QR que se imprime es el MISMO que ya trae el XML (Anexo §13.1: URL de consulta de la DIAN con el CUNE).
        'qr_url': qr,
    }
