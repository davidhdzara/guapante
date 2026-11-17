# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Armado del XML de la nota de ajuste de nómina electrónica (Python puro, sin Odoo).

Estas funciones vivían en ``models/l10n_co_ne_documento_mixin.py`` (``_ne_reemplazar``, ``_ne_eliminar``,
``_ne_cune_valores``) y solo leen un diccionario ``data`` (la forma de ``_collect_payslip_data``) y el predecesor:
no dependen de ningún campo del recibo. Se extraen para que el recibo (mixin) y el documento mensual armen la nota
con UNA sola implementación (doc 53 §23.16, D-3; mismo criterio que ``dian_respuesta``). El mixin conserva sus 3
nombres como envoltorios delgados: el comportamiento del recibo no cambia.
"""

from lxml import etree

# Secciones que la nota "Reemplazar" copia tal cual del documento (el XSD las admite todas).
_SECCIONES_REEMPLAZAR = (
    'periodo', 'numero_secuencia', 'lugar_generacion', 'proveedor_xml', 'informacion_general', 'empleador',
    'trabajador', 'pago', 'fechas_pagos', 'devengados', 'deducciones', 'devengados_total', 'deducciones_total',
    'comprobante_total')
# Secciones que admite <Eliminar> (Anexo §5.5.8, TipoNota=2; H-001): NO lleva periodo, trabajador, pago,
# devengados, deducciones ni totales.
_SECCIONES_ELIMINAR = ('lugar_generacion', 'proveedor_xml', 'informacion_general', 'empleador')


def predecesor(numero_pred, cune_pred, fecha_gen_pred):
    """Bloque ``predecesor`` de la nota: ``NumeroPred`` (prefijo + consecutivo del documento a reemplazar, no un trozo
    del CUNE), ``CUNEPred`` y ``FechaGenPred`` (``InformacionGeneral/@FechaGen`` de ese documento), NIAE190/NIAE192."""
    return {'NumeroPred': numero_pred, 'CUNEPred': cune_pred, 'FechaGenPred': fecha_gen_pred}


def reemplazar_desde(data, pred):
    """Sección ``<Reemplazar>`` de la nota de ajuste, reutilizando ``data`` (con el predecesor ``pred``).

    Lanza ``KeyError`` si falta una sección de ``data`` (igual que el código que sustituye)."""
    resultado = {'predecesor': pred}
    for seccion in _SECCIONES_REEMPLAZAR:
        resultado[seccion] = data[seccion]
    return resultado


def eliminar_desde(data, pred):
    """Sección ``<Eliminar>`` de la nota de ajuste (H-001, Anexo §5.5.8 TipoNota=2).

    Solo lleva lo que el XSD admite dentro de ``<Eliminar>``: predecesor, secuencia, lugar de generación, proveedor,
    QR, información general, notas y empleador. Sin ``CodigoTrabajador`` en la secuencia (el XSD de Eliminar no lo
    admite)."""
    numero_secuencia = {k: v for k, v in data['numero_secuencia'].items() if k != 'CodigoTrabajador'}
    resultado = {'predecesor': pred, 'numero_secuencia': numero_secuencia}
    for seccion in _SECCIONES_ELIMINAR:
        resultado[seccion] = data[seccion]
    return resultado


def cune_valores(es_eliminar, totales, doc_trab):
    """Valores variables del CUNE (ValDev, ValDed, ValTol, DocEmp), numeral 8.1.1.4 del Anexo.

    Nómina individual y nota Reemplazar: los totales y el documento del trabajador del propio documento. Nota
    Eliminar (H-001): el Anexo fija valores literales -- ValDev=ValDed=ValTol=0.00 y DocEmp=0 -- porque ese documento
    no lleva totales ni trabajador.

    Args:
        es_eliminar: True si es una nota de ajuste tipo Eliminar.
        totales: dict con ``DevengadosTotal``, ``DeduccionesTotal`` y ``ComprobanteTotal``.
        doc_trab: número de documento del trabajador ('' si no tiene).
    """
    if es_eliminar:
        return {'val_dev': '0.00', 'val_ded': '0.00', 'val_tol': '0.00', 'doc_trab': '0'}
    return {
        'val_dev': totales['DevengadosTotal'],
        'val_ded': totales['DeduccionesTotal'],
        'val_tol': totales['ComprobanteTotal'],
        'doc_trab': doc_trab,
    }


def fecha_gen_de_xml(xml_bytes):
    """``InformacionGeneral/@FechaGen`` de un XML de nómina (la fecha de emisión del documento predecesor), o ''.

    Lanza ``lxml.etree.XMLSyntaxError`` si el XML no se puede leer: el llamador decide si es un error claro."""
    raiz = etree.fromstring(xml_bytes)
    info = raiz.find('.//{*}InformacionGeneral')
    return info.get('FechaGen', '') if info is not None else ''
