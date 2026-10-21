"""Constructor de XML para Nómina Electrónica DIAN — Colombia.

Genera XML de Nómina Individual Electrónica y Nómina Individual de
Ajuste Electrónica según el XSD v1.0.6 del Anexo Técnico DIAN.

Funciones principales:
    - build_nomina_individual(data) -> bytes
    - build_nota_ajuste(data) -> bytes

El parámetro ``data`` es un diccionario con llaves que reflejan la
estructura del XML (empleador, trabajador, periodo, devengados,
deducciones, etc.).  Cada sección es opcional salvo las marcadas
como ``minOccurs=1`` en el XSD.

Dependencias externas:
    - lxml (pip install lxml)

Sin dependencias de Odoo.
"""

import math
from typing import Any, Optional, Union
from lxml import etree

from ._dict_to_xml import dict_to_xml

# =====================================================================
# Namespaces
# =====================================================================

NS_NOMINA = 'dian:gov:co:facturaelectronica:NominaIndividual'
NS_NOMINA_AJUSTE = (
    'dian:gov:co:facturaelectronica:NominaIndividualDeAjuste'
)
NS_EXT = (
    'urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonExtensionComponents-2'
)
NS_DS = 'http://www.w3.org/2000/09/xmldsig#'
NS_XADES = 'http://uri.etsi.org/01903/v1.3.2#'
NS_XADES141 = 'http://uri.etsi.org/01903/v1.4.1#'
NS_XS = 'http://www.w3.org/2001/XMLSchema-instance'
NS_XSD = 'http://www.w3.org/2001/XMLSchema-instance'

# Mapa común de prefijos
_NSMAP_NOMINA = {
    None: NS_NOMINA,
    'xs': NS_XS,
    'ds': NS_DS,
    'ext': NS_EXT,
    'xades': NS_XADES,
    'xades141': NS_XADES141,
    'xsi': NS_XSD,
}

_NSMAP_AJUSTE = {
    None: NS_NOMINA_AJUSTE,
    'xs': NS_XS,
    'ds': NS_DS,
    'ext': NS_EXT,
    'xades': NS_XADES,
    'xades141': NS_XADES141,
    'xsi': NS_XSD,
}


def _serialize(root: etree._Element) -> bytes:
    """Serializa el documento forzando ``xsi:schemaLocation``.

    ``xs`` y ``xsi`` apuntan a la MISMA URI (el Anexo DIAN exige declarar ambos, en ese
    orden). lxml escribe ``{URI}schemaLocation`` con el PRIMER prefijo del mapa (``xs:``),
    pero la DIAN (.NET SignedXml) canoniza el atributo con el ULTIMO prefijo declarado
    (``xsi:``). Si el texto dice ``xs:`` el digest del documento que verifica la DIAN no
    coincide con el firmado y responde ZE02. El documento aceptado por la DIAN lleva
    ``xmlns:xs`` luego ``xmlns:xsi`` y ``xsi:schemaLocation``.
    """
    xml = etree.tostring(
        root, xml_declaration=True, encoding='UTF-8', pretty_print=True,
    )
    return xml.replace(b' xs:schemaLocation=', b' xsi:schemaLocation=', 1)


# =====================================================================
# Helpers de construcción XML
# =====================================================================

def _el(
    parent: etree._Element,
    tag: str,
    text: Optional[str] = None,
    ns: Optional[str] = None,
    **attribs: str,
) -> etree._Element:
    """Crea un sub-elemento con texto opcional y atributos.

    Args:
        parent: Elemento padre.
        tag: Nombre de la etiqueta (sin namespace).
        text: Contenido textual del elemento (opcional).
        ns: Namespace URI. Si None, hereda del padre.
        **attribs: Atributos del elemento.

    Returns:
        El nuevo sub-elemento creado.
    """
    if ns is not None:
        full_tag = '{%s}%s' % (ns, tag)
    else:
        # Usar el namespace por defecto del padre
        parent_ns = etree.QName(parent.tag).namespace
        full_tag = '{%s}%s' % (parent_ns, tag) if parent_ns else tag

    elem = etree.SubElement(parent, full_tag)
    if text is not None:
        elem.text = str(text)
    for k, v in attribs.items():
        if v is not None:
            elem.set(k, str(v))
    return elem


def _attr(
    parent: etree._Element,
    tag: str,
    ns: Optional[str] = None,
    **attribs: str,
) -> etree._Element:
    """Crea un sub-elemento vacío solo con atributos.

    Igual que _el() pero sin texto. Útil para elementos como
    <Basico DiasTrabajados="30" SueldoTrabajado="1500000.00"/>.

    Args:
        parent: Elemento padre.
        tag: Nombre de la etiqueta.
        ns: Namespace URI opcional.
        **attribs: Atributos del elemento.

    Returns:
        El nuevo sub-elemento creado.
    """
    return _el(parent, tag, text=None, ns=ns, **attribs)


def _fmt(value: Union[int, float, str, None], decimals: int = 2) -> str:
    """Formatea un valor numérico a string con N decimales truncados.

    El Anexo Técnico DIAN exige decimales *truncados* (no redondeados).
    Se trunca hacia cero para coincidir con el formato del CUNE y evitar
    discrepancias entre los totales del XML y el CUNE.

    Args:
        value: Valor a formatear. Si None o vacío, retorna '0.00'.
        decimals: Cantidad de decimales.

    Returns:
        String formateado.
    """
    if value is None or value == '':
        return '0.' + '0' * decimals
    factor = 10 ** decimals
    truncated = math.trunc(float(value) * factor) / factor
    return ('%%.%df' % decimals) % truncated


def _get(data: dict, *keys, default=None):
    """Acceso seguro a diccionarios anidados.

    Args:
        data: Diccionario fuente.
        *keys: Cadena de llaves para acceso anidado.
        default: Valor por defecto si no existe.

    Returns:
        Valor encontrado o default.
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


# =====================================================================
# Secciones comunes (usadas por nómina y ajuste)
# =====================================================================

def _add_ubl_extensions(parent: etree._Element) -> etree._Element:
    """Agrega el placeholder ext:UBLExtensions para la firma digital.

    Args:
        parent: Elemento raíz del XML.

    Returns:
        El elemento UBLExtensions creado.
    """
    return etree.SubElement(parent, '{%s}UBLExtensions' % NS_EXT)


def _add_periodo(parent: etree._Element, data: dict) -> None:
    """Agrega el elemento Periodo con sus atributos.

    Args:
        parent: Elemento padre.
        data: Dict con llaves: FechaIngreso, FechaRetiro,
              FechaLiquidacionInicio, FechaLiquidacionFin,
              TiempoLaborado, FechaGen.
    """
    attribs = {
        'FechaIngreso': data.get('FechaIngreso', ''),
        'FechaLiquidacionInicio': data.get(
            'FechaLiquidacionInicio', ''),
        'FechaLiquidacionFin': data.get('FechaLiquidacionFin', ''),
        'TiempoLaborado': str(data.get('TiempoLaborado', '0')),
        'FechaGen': data.get('FechaGen', ''),
    }
    # FechaRetiro es opcional según el XSD
    if data.get('FechaRetiro'):
        attribs['FechaRetiro'] = data['FechaRetiro']

    _attr(parent, 'Periodo', **attribs)


def _add_numero_secuencia(parent: etree._Element, data: dict) -> None:
    """Agrega NumeroSecuenciaXML.

    Args:
        parent: Elemento padre.
        data: Dict con llaves: Prefijo, Consecutivo, Numero,
              CodigoTrabajador (opcional).
    """
    attribs = {
        'Consecutivo': str(data.get('Consecutivo', '')),
        'Numero': str(data.get('Numero', '')),
    }
    if data.get('Prefijo'):
        attribs['Prefijo'] = data['Prefijo']
    if data.get('CodigoTrabajador'):
        attribs['CodigoTrabajador'] = str(data['CodigoTrabajador'])

    _attr(parent, 'NumeroSecuenciaXML', **attribs)


def _add_lugar_generacion(parent: etree._Element, data: dict) -> None:
    """Agrega LugarGeneracionXML.

    Args:
        parent: Elemento padre.
        data: Dict con llaves: Pais, DepartamentoEstado,
              MunicipioCiudad, Idioma.
    """
    _attr(
        parent, 'LugarGeneracionXML',
        Pais=data.get('Pais', 'CO'),
        DepartamentoEstado=str(data.get('DepartamentoEstado', '')),
        MunicipioCiudad=str(data.get('MunicipioCiudad', '')),
        Idioma=data.get('Idioma', 'es'),
    )


def _add_proveedor_xml(parent: etree._Element, data: dict) -> None:
    """Agrega ProveedorXML.

    Args:
        parent: Elemento padre.
        data: Dict con llaves: NIT, DV, SoftwareID, SoftwareSC,
              RazonSocial, PrimerApellido, SegundoApellido,
              PrimerNombre, OtrosNombres (todos opcionales excepto
              NIT, DV, SoftwareID, SoftwareSC).
    """
    attribs = {
        'NIT': str(data.get('NIT', '')),
        'DV': str(data.get('DV', '')),
        'SoftwareID': data.get('SoftwareID', ''),
        'SoftwareSC': data.get('SoftwareSC', ''),
    }
    for campo in ('RazonSocial', 'PrimerApellido', 'SegundoApellido',
                  'PrimerNombre', 'OtrosNombres'):
        if data.get(campo):
            attribs[campo] = data[campo]

    _attr(parent, 'ProveedorXML', **attribs)


def _add_informacion_general(
    parent: etree._Element, data: dict,
) -> None:
    """Agrega InformacionGeneral.

    Args:
        parent: Elemento padre.
        data: Dict con llaves: Version, Ambiente, TipoXML, CUNE,
              EncripCUNE, FechaGen, HoraGen, PeriodoNomina,
              TipoMoneda, TRM (opcional).
    """
    attribs = {
        'Version': data.get('Version', 'V1.0: Documento Soporte'
                            ' de Pago de Nómina Electrónica'),
        'Ambiente': str(data.get('Ambiente', '2')),
        'TipoXML': str(data.get('TipoXML', '102')),
        'CUNE': data.get('CUNE', ''),
        'EncripCUNE': data.get('EncripCUNE', 'CUNE-SHA384'),
        'FechaGen': data.get('FechaGen', ''),
        'HoraGen': data.get('HoraGen', ''),
        'PeriodoNomina': str(data.get('PeriodoNomina', '5')),
        'TipoMoneda': data.get('TipoMoneda', 'COP'),
    }
    if data.get('TRM'):
        attribs['TRM'] = str(data['TRM'])

    _attr(parent, 'InformacionGeneral', **attribs)


def _add_empleador(parent: etree._Element, data: dict) -> None:
    """Agrega Empleador.

    Args:
        parent: Elemento padre.
        data: Dict con llaves: NIT, DV, Pais, DepartamentoEstado,
              MunicipioCiudad, Direccion, RazonSocial (opcionales),
              PrimerApellido, SegundoApellido, PrimerNombre,
              OtrosNombres (opcionales).
    """
    attribs = {
        'NIT': str(data.get('NIT', '')),
        'DV': str(data.get('DV', '')),
        'Pais': data.get('Pais', 'CO'),
        'DepartamentoEstado': str(
            data.get('DepartamentoEstado', '')),
        'MunicipioCiudad': str(data.get('MunicipioCiudad', '')),
        'Direccion': data.get('Direccion', ''),
    }
    for campo in ('RazonSocial', 'PrimerApellido', 'SegundoApellido',
                  'PrimerNombre', 'OtrosNombres'):
        if data.get(campo):
            attribs[campo] = data[campo]

    _attr(parent, 'Empleador', **attribs)


def _add_trabajador(parent: etree._Element, data: dict) -> None:
    """Agrega Trabajador.

    Args:
        parent: Elemento padre.
        data: Dict con llaves requeridas: TipoTrabajador,
              SubTipoTrabajador, AltoRiesgoPension, TipoDocumento,
              NumeroDocumento, PrimerApellido, SegundoApellido,
              PrimerNombre, LugarTrabajoPais,
              LugarTrabajoDepartamentoEstado,
              LugarTrabajoMunicipioCiudad, LugarTrabajoDireccion,
              SalarioIntegral, TipoContrato, Sueldo.
              Opcionales: OtrosNombres, CodigoTrabajador.
    """
    attribs = {
        'TipoTrabajador': str(data.get('TipoTrabajador', '01')),
        'SubTipoTrabajador': str(
            data.get('SubTipoTrabajador', '00')),
        'AltoRiesgoPension': str(
            data.get('AltoRiesgoPension', 'false')).lower(),
        'TipoDocumento': str(data.get('TipoDocumento', '13')),
        'NumeroDocumento': str(data.get('NumeroDocumento', '')),
        'PrimerApellido': data.get('PrimerApellido', ''),
        'SegundoApellido': data.get('SegundoApellido', ''),
        'PrimerNombre': data.get('PrimerNombre', ''),
        'LugarTrabajoPais': data.get('LugarTrabajoPais', 'CO'),
        'LugarTrabajoDepartamentoEstado': str(
            data.get('LugarTrabajoDepartamentoEstado', '')),
        'LugarTrabajoMunicipioCiudad': str(
            data.get('LugarTrabajoMunicipioCiudad', '')),
        'LugarTrabajoDireccion': data.get(
            'LugarTrabajoDireccion', ''),
        'SalarioIntegral': str(
            data.get('SalarioIntegral', 'false')).lower(),
        'TipoContrato': str(data.get('TipoContrato', '1')),
        'Sueldo': _fmt(data.get('Sueldo', 0)),
    }
    if data.get('OtrosNombres'):
        attribs['OtrosNombres'] = data['OtrosNombres']
    if data.get('CodigoTrabajador'):
        attribs['CodigoTrabajador'] = str(data['CodigoTrabajador'])

    _attr(parent, 'Trabajador', **attribs)


def _add_pago(parent: etree._Element, data: dict) -> None:
    """Agrega Pago.

    Args:
        parent: Elemento padre.
        data: Dict con llaves: Forma, Metodo, Banco (opc),
              TipoCuenta (opc), NumeroCuenta (opc).
    """
    attribs = {
        'Forma': str(data.get('Forma', '1')),
        'Metodo': str(data.get('Metodo', '1')),
    }
    for campo in ('Banco', 'TipoCuenta', 'NumeroCuenta'):
        if data.get(campo):
            attribs[campo] = data[campo]

    _attr(parent, 'Pago', **attribs)


def _add_fechas_pagos(
    parent: etree._Element, fechas: list[str],
) -> None:
    """Agrega FechasPagos con una o más FechaPago.

    Args:
        parent: Elemento padre.
        fechas: Lista de fechas en formato YYYY-MM-DD.
    """
    fp = _el(parent, 'FechasPagos')
    for fecha in fechas:
        _el(fp, 'FechaPago', text=str(fecha))


# =====================================================================
# Horas Extra — helper genérico
# =====================================================================

def _add_horas_extra(
    parent: etree._Element,
    wrapper_tag: str,
    item_tag: str,
    items: list[dict],
) -> None:
    """Agrega un bloque de horas extra (HEDs, HENs, HRNs, etc.).

    Args:
        parent: Elemento padre (Devengados).
        wrapper_tag: Tag contenedor (ej: 'HEDs').
        item_tag: Tag de cada ítem (ej: 'HED').
        items: Lista de dicts con llaves: HoraInicio, HoraFin,
               Cantidad, Porcentaje, Pago.
    """
    if not items:
        return
    wrapper = _el(parent, wrapper_tag)
    for item in items:
        attribs = {
            'Cantidad': str(item.get('Cantidad', '0')),
            'Porcentaje': _fmt(item.get('Porcentaje', 0)),
            'Pago': _fmt(item.get('Pago', 0)),
        }
        if item.get('HoraInicio'):
            attribs['HoraInicio'] = item['HoraInicio']
        if item.get('HoraFin'):
            attribs['HoraFin'] = item['HoraFin']
        _attr(wrapper, item_tag, **attribs)


# =====================================================================
# Devengados
# =====================================================================

def _add_devengados(parent: etree._Element, data: dict) -> None:
    """Agrega la sección completa de Devengados.

    Args:
        parent: Elemento padre.
        data: Dict con sub-dicts para cada concepto devengado.
              Llaves posibles: Basico (req), Transporte, HEDs, HENs,
              HRNs, HEDDFs, HRDDFs, HENDFs, HRNDFs, Vacaciones,
              Primas, Cesantias, Incapacidades, Licencias,
              Bonificaciones, Auxilios, HuelgasLegales,
              OtrosConceptos, Compensaciones, BonoEPCTVs,
              Comisiones, PagosTerceros, Anticipos, Dotacion,
              ApoyoSost, Teletrabajo, BonifRetiro, Indemnizacion,
              Reintegro.
    """
    dev = _el(parent, 'Devengados')

    # --- Basico (requerido) ---
    basico = data.get('Basico', {})
    _attr(
        dev, 'Basico',
        DiasTrabajados=str(basico.get('DiasTrabajados', '30')),
        SueldoTrabajado=_fmt(basico.get('SueldoTrabajado', 0)),
    )

    # --- Transporte ---
    # AUD-DIAN-34 (2026-10-04): el commit 2e81fbd agregó ViaticoManuAlojS/
    # NS siempre en "0.00" por NIE072/073, siguiendo al pie el ejemplo del
    # Anexo Técnico (que SÍ los trae en "0.0"). Evidencia empírica real
    # contra el validador de habilitación de la DIAN hoy (3 envíos de
    # prueba comparados, un documento por ZipKey) contradice ese ejemplo:
    # con los atributos presentes en "0.00" la DIAN devuelve NIE072+NIE073;
    # quitándolos (dejando solo AuxilioTransporte) el rechazo desaparece.
    # No hay regla citable en el Anexo que lo explique -- el validador
    # real rechaza el atributo presente en cero, así que se omite cuando
    # el valor es 0, igual que el resto de atributos opcionales del XSD.
    transporte = data.get('Transporte')
    if transporte:
        if isinstance(transporte, dict):
            transporte = [transporte]
        for t in transporte:
            viatico_s = float(t.get('ViaticoManuAlojS') or 0)
            viatico_ns = float(t.get('ViaticoManuAlojNS') or 0)
            if (
                t.get('AuxilioTransporte') is None
                and viatico_s <= 0
                and viatico_ns <= 0
            ):
                continue
            attribs = {}
            if t.get('AuxilioTransporte') is not None:
                attribs['AuxilioTransporte'] = _fmt(
                    t['AuxilioTransporte'])
            if viatico_s > 0:
                attribs['ViaticoManuAlojS'] = _fmt(viatico_s)
            if viatico_ns > 0:
                attribs['ViaticoManuAlojNS'] = _fmt(viatico_ns)
            _attr(dev, 'Transporte', **attribs)

    # --- Horas Extra ---
    _HORAS_EXTRA = [
        ('HEDs', 'HED'), ('HENs', 'HEN'), ('HRNs', 'HRN'),
        ('HEDDFs', 'HEDDF'), ('HRDDFs', 'HRDDF'),
        ('HENDFs', 'HENDF'), ('HRNDFs', 'HRNDF'),
    ]
    for wrapper, item in _HORAS_EXTRA:
        items = data.get(wrapper, [])
        if items:
            _add_horas_extra(dev, wrapper, item, items)

    # --- Vacaciones ---
    vac_data = data.get('Vacaciones')
    if vac_data:
        vac = _el(dev, 'Vacaciones')
        for vc in vac_data.get('VacacionesComunes', []):
            attribs = {
                'Cantidad': str(vc.get('Cantidad', '0')),
                'Pago': _fmt(vc.get('Pago', 0)),
            }
            if vc.get('FechaInicio'):
                attribs['FechaInicio'] = vc['FechaInicio']
            if vc.get('FechaFin'):
                attribs['FechaFin'] = vc['FechaFin']
            _attr(vac, 'VacacionesComunes', **attribs)

        for vcomp in vac_data.get('VacacionesCompensadas', []):
            _attr(
                vac, 'VacacionesCompensadas',
                Cantidad=str(vcomp.get('Cantidad', '0')),
                Pago=_fmt(vcomp.get('Pago', 0)),
            )

    # --- Primas ---
    primas = data.get('Primas')
    if primas:
        attribs = {
            'Cantidad': str(primas.get('Cantidad', '0')),
            'Pago': _fmt(primas.get('Pago', 0)),
        }
        if primas.get('PagoNS') is not None:
            attribs['PagoNS'] = _fmt(primas['PagoNS'])
        _attr(dev, 'Primas', **attribs)

    # --- Cesantias ---
    ces = data.get('Cesantias')
    if ces:
        _attr(
            dev, 'Cesantias',
            Pago=_fmt(ces.get('Pago', 0)),
            Porcentaje=_fmt(ces.get('Porcentaje', 0)),
            PagoIntereses=_fmt(ces.get('PagoIntereses', 0)),
        )

    # --- Incapacidades ---
    incap_list = data.get('Incapacidades', [])
    if incap_list:
        incaps = _el(dev, 'Incapacidades')
        for inc in incap_list:
            attribs = {
                'Cantidad': str(inc.get('Cantidad', '0')),
                'Tipo': str(inc.get('Tipo', '1')),
                'Pago': _fmt(inc.get('Pago', 0)),
            }
            if inc.get('FechaInicio'):
                attribs['FechaInicio'] = inc['FechaInicio']
            if inc.get('FechaFin'):
                attribs['FechaFin'] = inc['FechaFin']
            _attr(incaps, 'Incapacidad', **attribs)

    # --- Licencias ---
    lic_data = data.get('Licencias')
    if lic_data:
        lics = _el(dev, 'Licencias')
        for lmp in lic_data.get('LicenciaMP', []):
            attribs = {
                'Cantidad': str(lmp.get('Cantidad', '0')),
                'Pago': _fmt(lmp.get('Pago', 0)),
            }
            if lmp.get('FechaInicio'):
                attribs['FechaInicio'] = lmp['FechaInicio']
            if lmp.get('FechaFin'):
                attribs['FechaFin'] = lmp['FechaFin']
            _attr(lics, 'LicenciaMP', **attribs)

        for lr in lic_data.get('LicenciaR', []):
            attribs = {
                'Cantidad': str(lr.get('Cantidad', '0')),
                'Pago': _fmt(lr.get('Pago', 0)),
            }
            if lr.get('FechaInicio'):
                attribs['FechaInicio'] = lr['FechaInicio']
            if lr.get('FechaFin'):
                attribs['FechaFin'] = lr['FechaFin']
            _attr(lics, 'LicenciaR', **attribs)

        for lnr in lic_data.get('LicenciaNR', []):
            attribs = {
                'Cantidad': str(lnr.get('Cantidad', '0')),
            }
            if lnr.get('FechaInicio'):
                attribs['FechaInicio'] = lnr['FechaInicio']
            if lnr.get('FechaFin'):
                attribs['FechaFin'] = lnr['FechaFin']
            _attr(lics, 'LicenciaNR', **attribs)

    # --- Bonificaciones ---
    bonif_list = data.get('Bonificaciones', [])
    if bonif_list:
        bonifs = _el(dev, 'Bonificaciones')
        for b in bonif_list:
            attribs = {}
            if b.get('BonificacionS') is not None:
                attribs['BonificacionS'] = _fmt(b['BonificacionS'])
            if b.get('BonificacionNS') is not None:
                attribs['BonificacionNS'] = _fmt(b['BonificacionNS'])
            _attr(bonifs, 'Bonificacion', **attribs)

    # --- Auxilios ---
    aux_list = data.get('Auxilios', [])
    if aux_list:
        auxs = _el(dev, 'Auxilios')
        for a in aux_list:
            attribs = {}
            if a.get('AuxilioS') is not None:
                attribs['AuxilioS'] = _fmt(a['AuxilioS'])
            if a.get('AuxilioNS') is not None:
                attribs['AuxilioNS'] = _fmt(a['AuxilioNS'])
            _attr(auxs, 'Auxilio', **attribs)

    # --- HuelgasLegales ---
    huelgas = data.get('HuelgasLegales', [])
    if huelgas:
        hl = _el(dev, 'HuelgasLegales')
        for h in huelgas:
            attribs = {
                'Cantidad': str(h.get('Cantidad', '0')),
            }
            if h.get('FechaInicio'):
                attribs['FechaInicio'] = h['FechaInicio']
            if h.get('FechaFin'):
                attribs['FechaFin'] = h['FechaFin']
            _attr(hl, 'HuelgaLegal', **attribs)

    # --- OtrosConceptos ---
    otros = data.get('OtrosConceptos', [])
    if otros:
        oc = _el(dev, 'OtrosConceptos')
        for o in otros:
            attribs = {
                'DescripcionConcepto': o.get(
                    'DescripcionConcepto', ''),
            }
            if o.get('ConceptoS') is not None:
                attribs['ConceptoS'] = _fmt(o['ConceptoS'])
            if o.get('ConceptoNS') is not None:
                attribs['ConceptoNS'] = _fmt(o['ConceptoNS'])
            _attr(oc, 'OtroConcepto', **attribs)

    # --- Compensaciones ---
    comp_list = data.get('Compensaciones', [])
    if comp_list:
        comps = _el(dev, 'Compensaciones')
        for c in comp_list:
            _attr(
                comps, 'Compensacion',
                CompensacionO=_fmt(c.get('CompensacionO', 0)),
                CompensacionE=_fmt(c.get('CompensacionE', 0)),
            )

    # --- BonoEPCTVs ---
    bonos = data.get('BonoEPCTVs', [])
    if bonos:
        bono_wrap = _el(dev, 'BonoEPCTVs')
        for bn in bonos:
            attribs = {}
            if bn.get('PagoS') is not None:
                attribs['PagoS'] = _fmt(bn['PagoS'])
            if bn.get('PagoNS') is not None:
                attribs['PagoNS'] = _fmt(bn['PagoNS'])
            if bn.get('PagoAlimentacionS') is not None:
                attribs['PagoAlimentacionS'] = _fmt(
                    bn['PagoAlimentacionS'])
            if bn.get('PagoAlimentacionNS') is not None:
                attribs['PagoAlimentacionNS'] = _fmt(
                    bn['PagoAlimentacionNS'])
            _attr(bono_wrap, 'BonoEPCTV', **attribs)

    # --- Comisiones ---
    comisiones = data.get('Comisiones', [])
    if comisiones:
        com_wrap = _el(dev, 'Comisiones')
        for c in comisiones:
            _el(com_wrap, 'Comision', text=_fmt(c))

    # --- PagosTerceros ---
    pagos_t = data.get('PagosTerceros', [])
    if pagos_t:
        pt_wrap = _el(dev, 'PagosTerceros')
        for pt in pagos_t:
            _el(pt_wrap, 'PagoTercero', text=_fmt(pt))

    # --- Anticipos ---
    anticipos = data.get('Anticipos', [])
    if anticipos:
        ant_wrap = _el(dev, 'Anticipos')
        for a in anticipos:
            _el(ant_wrap, 'Anticipo', text=_fmt(a))

    # --- Elementos simples opcionales ---
    _SIMPLE_DEVENGADOS = [
        'Dotacion', 'ApoyoSost', 'Teletrabajo',
        'BonifRetiro', 'Indemnizacion', 'Reintegro',
    ]
    for campo in _SIMPLE_DEVENGADOS:
        val = data.get(campo)
        if val is not None:
            _el(dev, campo, text=_fmt(val))


# =====================================================================
# Deducciones
# =====================================================================

def _add_deducciones(parent: etree._Element, data: dict) -> None:
    """Agrega la sección completa de Deducciones.

    Args:
        parent: Elemento padre.
        data: Dict con sub-dicts para cada concepto deducido.
              Llaves: Salud (req), FondoPension (req), FondoSP,
              Sindicatos, Sanciones, Libranzas, PagosTerceros,
              Anticipos, OtrasDeducciones, PensionVoluntaria,
              RetencionFuente, AFC, Cooperativa, EmbargoFiscal,
              PlanComplementarios, Educacion, Reintegro, Deuda.
    """
    ded = _el(parent, 'Deducciones')

    # --- Salud (requerido) ---
    salud = data.get('Salud', {})
    _attr(
        ded, 'Salud',
        Porcentaje=_fmt(salud.get('Porcentaje', 4)),
        Deduccion=_fmt(salud.get('Deduccion', 0)),
    )

    # --- FondoPension (requerido) ---
    pension = data.get('FondoPension', {})
    _attr(
        ded, 'FondoPension',
        Porcentaje=_fmt(pension.get('Porcentaje', 4)),
        Deduccion=_fmt(pension.get('Deduccion', 0)),
    )

    # --- FondoSP ---
    fsp = data.get('FondoSP')
    if fsp:
        attribs = {}
        if fsp.get('Porcentaje') is not None:
            attribs['Porcentaje'] = _fmt(fsp['Porcentaje'])
        if fsp.get('DeduccionSP') is not None:
            attribs['DeduccionSP'] = _fmt(fsp['DeduccionSP'])
        if fsp.get('PorcentajeSub') is not None:
            attribs['PorcentajeSub'] = _fmt(fsp['PorcentajeSub'])
        if fsp.get('DeduccionSub') is not None:
            attribs['DeduccionSub'] = _fmt(fsp['DeduccionSub'])
        if attribs:
            _attr(ded, 'FondoSP', **attribs)

    # --- Sindicatos ---
    sind_list = data.get('Sindicatos', [])
    if sind_list:
        sinds = _el(ded, 'Sindicatos')
        for s in sind_list:
            _attr(
                sinds, 'Sindicato',
                Porcentaje=_fmt(s.get('Porcentaje', 0)),
                Deduccion=_fmt(s.get('Deduccion', 0)),
            )

    # --- Sanciones ---
    sanc_list = data.get('Sanciones', [])
    if sanc_list:
        sancs = _el(ded, 'Sanciones')
        for s in sanc_list:
            _attr(
                sancs, 'Sancion',
                SancionPublic=_fmt(s.get('SancionPublic', 0)),
                SancionPriv=_fmt(s.get('SancionPriv', 0)),
            )

    # --- Libranzas ---
    lib_list = data.get('Libranzas', [])
    if lib_list:
        libs = _el(ded, 'Libranzas')
        for l in lib_list:
            _attr(
                libs, 'Libranza',
                Descripcion=l.get('Descripcion', ''),
                Deduccion=_fmt(l.get('Deduccion', 0)),
            )

    # --- PagosTerceros ---
    pagos_t = data.get('PagosTerceros', [])
    if pagos_t:
        pt_wrap = _el(ded, 'PagosTerceros')
        for pt in pagos_t:
            _el(pt_wrap, 'PagoTercero', text=_fmt(pt))

    # --- Anticipos ---
    anticipos = data.get('Anticipos', [])
    if anticipos:
        ant_wrap = _el(ded, 'Anticipos')
        for a in anticipos:
            _el(ant_wrap, 'Anticipo', text=_fmt(a))

    # --- OtrasDeducciones ---
    otras = data.get('OtrasDeducciones', [])
    if otras:
        od_wrap = _el(ded, 'OtrasDeducciones')
        for o in otras:
            _el(od_wrap, 'OtraDeduccion', text=_fmt(o))

    # --- Elementos simples opcionales ---
    _SIMPLE_DEDUCCIONES = [
        'PensionVoluntaria', 'RetencionFuente', 'AFC',
        'Cooperativa', 'EmbargoFiscal', 'PlanComplementarios',
        'Educacion', 'Reintegro', 'Deuda',
    ]
    for campo in _SIMPLE_DEDUCCIONES:
        val = data.get(campo)
        if val is not None:
            _el(ded, campo, text=_fmt(val))


# =====================================================================
# build_nomina_individual — Función principal
# =====================================================================

def build_nomina_individual(data: dict) -> bytes:
    """Construye el XML completo de Nómina Individual Electrónica.

    Genera un XML válido según el XSD
    NominaIndividualElectronicaXSDV1.0.6.xsd de la DIAN.

    El XML resultante incluye el placeholder ext:UBLExtensions para
    la firma digital (debe firmarse con xml_signer.sign_xml después).

    Args:
        data: Diccionario con la estructura completa del documento.
              Llaves principales:
              - periodo (dict): Datos del periodo de liquidación.
              - numero_secuencia (dict): Prefijo, consecutivo, etc.
              - lugar_generacion (dict): País, depto, municipio.
              - proveedor_xml (dict): Datos del proveedor de software.
              - codigo_qr (str): URL del código QR.
              - informacion_general (dict): CUNE, fechas, ambiente.
              - notas (str o list[str]): Notas opcionales.
              - empleador (dict): Datos del empleador.
              - trabajador (dict): Datos del trabajador.
              - pago (dict): Forma y método de pago.
              - fechas_pagos (list[str]): Fechas de pago.
              - devengados (dict): Todos los conceptos devengados.
              - deducciones (dict): Todas las deducciones.
              - redondeo (float): Valor de redondeo.
              - devengados_total (float): Total devengados.
              - deducciones_total (float): Total deducciones.
              - comprobante_total (float): Total comprobante.
              - novedad (dict): Opcional — CUNENov y valor bool.

    Returns:
        XML como bytes UTF-8 con declaración XML.

    Examples:
        >>> data = {
        ...     'periodo': {
        ...         'FechaIngreso': '2023-01-01',
        ...         'FechaLiquidacionInicio': '2024-01-01',
        ...         'FechaLiquidacionFin': '2024-01-31',
        ...         'TiempoLaborado': '365',
        ...         'FechaGen': '2024-01-31',
        ...     },
        ...     'numero_secuencia': {
        ...         'Prefijo': 'NE', 'Consecutivo': '1',
        ...         'Numero': 'NE1',
        ...     },
        ...     # ... más secciones ...
        ... }
        >>> xml_bytes = build_nomina_individual(data)
        >>> xml_bytes[:5]
        b'<?xml'
    """
    # Raíz: NominaIndividual
    root = etree.Element(
        '{%s}NominaIndividual' % NS_NOMINA,
        nsmap=_NSMAP_NOMINA,
    )
    root.set('SchemaLocation', '')
    root.set(
        '{%s}schemaLocation' % NS_XSD,
        '%s NominaIndividualElectronicaXSD.xsd' % NS_NOMINA,
    )

    # 1. UBLExtensions (placeholder para firma)
    _add_ubl_extensions(root)

    # 2. Novedad (opcional)
    novedad = data.get('novedad')
    if novedad:
        nov_elem = _el(
            root, 'Novedad',
            text=str(novedad.get('value', 'false')).lower(),
            CUNENov=novedad.get('CUNENov', ''),
        )

    # 3. Periodo (requerido)
    _add_periodo(root, data.get('periodo', {}))

    # 4. NumeroSecuenciaXML (requerido)
    _add_numero_secuencia(root, data.get('numero_secuencia', {}))

    # 5. LugarGeneracionXML (requerido)
    _add_lugar_generacion(root, data.get('lugar_generacion', {}))

    # 6. ProveedorXML (requerido)
    _add_proveedor_xml(root, data.get('proveedor_xml', {}))

    # 7. CodigoQR (requerido)
    _el(root, 'CodigoQR', text=data.get('codigo_qr', ''))

    # 8. InformacionGeneral (requerido)
    _add_informacion_general(
        root, data.get('informacion_general', {}))

    # 9. Notas (opcional, puede ser múltiple)
    notas = data.get('notas')
    if notas:
        if isinstance(notas, str):
            notas = [notas]
        for nota in notas:
            _el(root, 'Notas', text=nota)

    # 10. Empleador (requerido)
    _add_empleador(root, data.get('empleador', {}))

    # 11. Trabajador (requerido)
    _add_trabajador(root, data.get('trabajador', {}))

    # 12. Pago (requerido)
    _add_pago(root, data.get('pago', {}))

    # 13. FechasPagos (requerido)
    _add_fechas_pagos(root, data.get('fechas_pagos', []))

    # 14. Devengados (requerido)
    _add_devengados(root, data.get('devengados', {}))

    # 15. Deducciones (requerido)
    _add_deducciones(root, data.get('deducciones', {}))

    # 16. Redondeo (opcional)
    if data.get('redondeo') is not None:
        _el(root, 'Redondeo', text=_fmt(data['redondeo']))

    # 17. DevengadosTotal (requerido)
    _el(root, 'DevengadosTotal',
        text=_fmt(data.get('devengados_total', 0)))

    # 18. DeduccionesTotal (requerido)
    _el(root, 'DeduccionesTotal',
        text=_fmt(data.get('deducciones_total', 0)))

    # 19. ComprobanteTotal (requerido)
    _el(root, 'ComprobanteTotal',
        text=_fmt(data.get('comprobante_total', 0)))

    return _serialize(root)


# =====================================================================
# build_nota_ajuste — Nómina Individual de Ajuste
# =====================================================================

def build_nota_ajuste(data: dict) -> bytes:
    """Construye el XML de Nómina Individual de Ajuste Electrónica.

    Genera un XML válido según el XSD de ajuste de la DIAN.
    El ajuste puede ser de tipo Reemplazar o Eliminar.

    Args:
        data: Diccionario con la estructura del ajuste.
              Llaves principales:
              - tipo_nota (str): Código del tipo de nota
                  ('1' = Reemplazar, '2' = Eliminar).
              - reemplazar (dict): Datos completos de reemplazo
                  (contiene las mismas secciones que nómina individual
                  más 'predecesor' con NumeroPred, CUNEPred,
                  FechaGenPred).
              - eliminar (dict): Datos de eliminación
                  (predecesor + secciones reducidas).

    Returns:
        XML como bytes UTF-8 con declaración XML.
    """
    root = etree.Element(
        '{%s}NominaIndividualDeAjuste' % NS_NOMINA_AJUSTE,
        nsmap=_NSMAP_AJUSTE,
    )
    root.set('SchemaLocation', '')
    root.set(
        '{%s}schemaLocation' % NS_XSD,
        '%s NominaIndividualDeAjusteElectronicaXSD.xsd'
        % NS_NOMINA_AJUSTE,
    )

    # 1. UBLExtensions (placeholder para firma)
    _add_ubl_extensions(root)

    # 2. TipoNota (requerido)
    _el(root, 'TipoNota', text=str(data.get('tipo_nota', '1')))

    # 3. Reemplazar (opcional)
    reemplazar = data.get('reemplazar')
    if reemplazar:
        _build_reemplazar(root, reemplazar)

    # 4. Eliminar (opcional)
    eliminar = data.get('eliminar')
    if eliminar:
        _build_eliminar(root, eliminar)

    return _serialize(root)


def _build_reemplazar(
    parent: etree._Element, data: dict,
) -> None:
    """Construye la sección <Reemplazar> del ajuste.

    Contiene ReemplazandoPredecesor + todas las secciones de nómina.

    Args:
        parent: Elemento raíz del ajuste.
        data: Dict con 'predecesor' (dict con NumeroPred, CUNEPred,
              FechaGenPred) y las mismas llaves que build_nomina_individual.
    """
    remp = _el(parent, 'Reemplazar')

    # ReemplazandoPredecesor
    pred = data.get('predecesor', {})
    _attr(
        remp, 'ReemplazandoPredecesor',
        NumeroPred=str(pred.get('NumeroPred', '')),
        CUNEPred=str(pred.get('CUNEPred', '')),
        FechaGenPred=str(pred.get('FechaGenPred', '')),
    )

    # Periodo
    _add_periodo(remp, data.get('periodo', {}))

    # NumeroSecuenciaXML
    _add_numero_secuencia(remp, data.get('numero_secuencia', {}))

    # LugarGeneracionXML
    _add_lugar_generacion(remp, data.get('lugar_generacion', {}))

    # ProveedorXML
    _add_proveedor_xml(remp, data.get('proveedor_xml', {}))

    # CodigoQR
    _el(remp, 'CodigoQR', text=data.get('codigo_qr', ''))

    # InformacionGeneral
    _add_informacion_general(
        remp, data.get('informacion_general', {}))

    # Notas
    notas = data.get('notas')
    if notas:
        if isinstance(notas, str):
            notas = [notas]
        for nota in notas:
            _el(remp, 'Notas', text=nota)

    # Empleador
    _add_empleador(remp, data.get('empleador', {}))

    # Trabajador
    _add_trabajador(remp, data.get('trabajador', {}))

    # Pago
    _add_pago(remp, data.get('pago', {}))

    # FechasPagos
    _add_fechas_pagos(remp, data.get('fechas_pagos', []))

    # Devengados
    _add_devengados(remp, data.get('devengados', {}))

    # Deducciones
    _add_deducciones(remp, data.get('deducciones', {}))

    # Redondeo
    if data.get('redondeo') is not None:
        _el(remp, 'Redondeo', text=_fmt(data['redondeo']))

    # Totales
    _el(remp, 'DevengadosTotal',
        text=_fmt(data.get('devengados_total', 0)))
    _el(remp, 'DeduccionesTotal',
        text=_fmt(data.get('deducciones_total', 0)))
    _el(remp, 'ComprobanteTotal',
        text=_fmt(data.get('comprobante_total', 0)))


def _build_eliminar(
    parent: etree._Element, data: dict,
) -> None:
    """Construye la sección <Eliminar> del ajuste.

    Contiene EliminandoPredecesor + secciones mínimas requeridas.

    Args:
        parent: Elemento raíz del ajuste.
        data: Dict con 'predecesor' (dict con NumeroPred, CUNEPred,
              FechaGenPred) y secciones reducidas.
    """
    elim = _el(parent, 'Eliminar')

    # EliminandoPredecesor
    pred = data.get('predecesor', {})
    _attr(
        elim, 'EliminandoPredecesor',
        NumeroPred=str(pred.get('NumeroPred', '')),
        CUNEPred=str(pred.get('CUNEPred', '')),
        FechaGenPred=str(pred.get('FechaGenPred', '')),
    )

    # NumeroSecuenciaXML
    _add_numero_secuencia(elim, data.get('numero_secuencia', {}))

    # LugarGeneracionXML
    _add_lugar_generacion(elim, data.get('lugar_generacion', {}))

    # ProveedorXML
    _add_proveedor_xml(elim, data.get('proveedor_xml', {}))

    # CodigoQR
    _el(elim, 'CodigoQR', text=data.get('codigo_qr', ''))

    # InformacionGeneral
    _add_informacion_general(
        elim, data.get('informacion_general', {}))

    # Notas
    notas = data.get('notas')
    if notas:
        if isinstance(notas, str):
            notas = [notas]
        for nota in notas:
            _el(elim, 'Notas', text=nota)

    # Empleador
    _add_empleador(elim, data.get('empleador', {}))


# =====================================================================
# doc 24 -- Fase 1: migración a dict_to_xml (secciones simples)
#
# Funciones nuevas, en paralelo a las _add_X() de arriba (que siguen
# siendo las que realmente usa build_nomina_individual()/
# build_nota_ajuste() por ahora) -- NO están todavía conectadas al
# flujo público. Cubren las 9 secciones "simples" del documento raíz
# (Periodo, NumeroSecuenciaXML, LugarGeneracionXML, ProveedorXML,
# InformacionGeneral, Empleador, Trabajador, Pago, FechasPagos).
# Devengados/Deducciones (la parte grande y de mayor riesgo, ~380
# líneas combinadas) quedan para la Fase 2, doc 24 §8.
#
# Patrón: 1 función _get_X_node(data) -> dict por cada _add_X(parent,
# data) existente, mismo criterio que _add_invoice_header_nodes en
# account_edi_ubl_cii/models/account_edi_xml_ubl_20.py (la referencia
# elegida en doc 24 §2). _fmt()/_get() no cambian -- siguen
# produciendo los mismos strings, solo que ahora van a valores de dict
# en vez de argumentos de _el()/_attr().
# =====================================================================

def _get_periodo_node(data: dict) -> dict:
    """Equivalente dict de _add_periodo(). data = sub-dict 'periodo'."""
    node = {
        'FechaIngreso': data.get('FechaIngreso', ''),
        'FechaLiquidacionInicio': data.get('FechaLiquidacionInicio', ''),
        'FechaLiquidacionFin': data.get('FechaLiquidacionFin', ''),
        'TiempoLaborado': str(data.get('TiempoLaborado', '0')),
        'FechaGen': data.get('FechaGen', ''),
    }
    if data.get('FechaRetiro'):
        node['FechaRetiro'] = data['FechaRetiro']
    return node


def _get_numero_secuencia_node(data: dict) -> dict:
    """Equivalente dict de _add_numero_secuencia(). data = sub-dict 'numero_secuencia'."""
    node = {
        'Consecutivo': str(data.get('Consecutivo', '')),
        'Numero': str(data.get('Numero', '')),
    }
    if data.get('Prefijo'):
        node['Prefijo'] = data['Prefijo']
    if data.get('CodigoTrabajador'):
        node['CodigoTrabajador'] = str(data['CodigoTrabajador'])
    return node


def _get_lugar_generacion_node(data: dict) -> dict:
    """Equivalente dict de _add_lugar_generacion(). data = sub-dict 'lugar_generacion'."""
    return {
        'Pais': data.get('Pais', 'CO'),
        'DepartamentoEstado': str(data.get('DepartamentoEstado', '')),
        'MunicipioCiudad': str(data.get('MunicipioCiudad', '')),
        'Idioma': data.get('Idioma', 'es'),
    }


def _get_proveedor_xml_node(data: dict) -> dict:
    """Equivalente dict de _add_proveedor_xml(). data = sub-dict 'proveedor_xml'."""
    node = {
        'NIT': str(data.get('NIT', '')),
        'DV': str(data.get('DV', '')),
        'SoftwareID': data.get('SoftwareID', ''),
        'SoftwareSC': data.get('SoftwareSC', ''),
    }
    for campo in ('RazonSocial', 'PrimerApellido', 'SegundoApellido',
                  'PrimerNombre', 'OtrosNombres'):
        if data.get(campo):
            node[campo] = data[campo]
    return node


def _get_informacion_general_node(data: dict) -> dict:
    """Equivalente dict de _add_informacion_general(). data = sub-dict 'informacion_general'."""
    node = {
        'Version': data.get(
            'Version',
            'V1.0: Documento Soporte de Pago de Nómina Electrónica',
        ),
        'Ambiente': str(data.get('Ambiente', '2')),
        'TipoXML': str(data.get('TipoXML', '102')),
        'CUNE': data.get('CUNE', ''),
        'EncripCUNE': data.get('EncripCUNE', 'CUNE-SHA384'),
        'FechaGen': data.get('FechaGen', ''),
        'HoraGen': data.get('HoraGen', ''),
        'PeriodoNomina': str(data.get('PeriodoNomina', '5')),
        'TipoMoneda': data.get('TipoMoneda', 'COP'),
    }
    if data.get('TRM'):
        node['TRM'] = str(data['TRM'])
    return node


def _get_empleador_node(data: dict) -> dict:
    """Equivalente dict de _add_empleador(). data = sub-dict 'empleador'."""
    node = {
        'NIT': str(data.get('NIT', '')),
        'DV': str(data.get('DV', '')),
        'Pais': data.get('Pais', 'CO'),
        'DepartamentoEstado': str(data.get('DepartamentoEstado', '')),
        'MunicipioCiudad': str(data.get('MunicipioCiudad', '')),
        'Direccion': data.get('Direccion', ''),
    }
    for campo in ('RazonSocial', 'PrimerApellido', 'SegundoApellido',
                  'PrimerNombre', 'OtrosNombres'):
        if data.get(campo):
            node[campo] = data[campo]
    return node


def _get_trabajador_node(data: dict) -> dict:
    """Equivalente dict de _add_trabajador(). data = sub-dict 'trabajador'."""
    node = {
        'TipoTrabajador': str(data.get('TipoTrabajador', '01')),
        'SubTipoTrabajador': str(data.get('SubTipoTrabajador', '00')),
        'AltoRiesgoPension': str(data.get('AltoRiesgoPension', 'false')).lower(),
        'TipoDocumento': str(data.get('TipoDocumento', '13')),
        'NumeroDocumento': str(data.get('NumeroDocumento', '')),
        'PrimerApellido': data.get('PrimerApellido', ''),
        'SegundoApellido': data.get('SegundoApellido', ''),
        'PrimerNombre': data.get('PrimerNombre', ''),
        'LugarTrabajoPais': data.get('LugarTrabajoPais', 'CO'),
        'LugarTrabajoDepartamentoEstado': str(
            data.get('LugarTrabajoDepartamentoEstado', '')),
        'LugarTrabajoMunicipioCiudad': str(
            data.get('LugarTrabajoMunicipioCiudad', '')),
        'LugarTrabajoDireccion': data.get('LugarTrabajoDireccion', ''),
        'SalarioIntegral': str(data.get('SalarioIntegral', 'false')).lower(),
        'TipoContrato': str(data.get('TipoContrato', '1')),
        'Sueldo': _fmt(data.get('Sueldo', 0)),
    }
    if data.get('OtrosNombres'):
        node['OtrosNombres'] = data['OtrosNombres']
    if data.get('CodigoTrabajador'):
        node['CodigoTrabajador'] = str(data['CodigoTrabajador'])
    return node


def _get_pago_node(data: dict) -> dict:
    """Equivalente dict de _add_pago(). data = sub-dict 'pago'."""
    node = {
        'Forma': str(data.get('Forma', '1')),
        'Metodo': str(data.get('Metodo', '1')),
    }
    for campo in ('Banco', 'TipoCuenta', 'NumeroCuenta'):
        if data.get(campo):
            node[campo] = data[campo]
    return node


def _get_fechas_pagos_node(fechas: list[str]) -> dict:
    """Equivalente dict de _add_fechas_pagos(). fechas = lista 'fechas_pagos'."""
    return {
        'FechaPago': [{'_text': str(fecha)} for fecha in fechas],
    }


# =====================================================================
# Devengados / Deducciones / HorasExtra -- Fase 2 (doc 24 SS8, paso 3)
#
# Mismo patron que las 9 secciones simples de arriba: 1 funcion
# _get_X_node(data) -> dict por cada _add_X(parent, data) equivalente
# de mas arriba en este archivo (las funciones viejas, sin tocar, siguen
# siendo las que usa build_nomina_individual()/build_nota_ajuste() hoy).
#
# Regla clave para traducir "si no hay dato, no se genera el elemento"
# (el patron `if attribs: _attr(...)` / `if items: _el(...)` de las
# funciones viejas): dict_to_xml() YA hace esto automaticamente -- al
# final de renderizar cada nodo, si no tiene atributos, texto NI hijos,
# devuelve None en vez del elemento (ver dict_to_xml() en _dict_to_xml.py,
# ultima linea antes de `return element`), y el padre lo omite solo. Por
# eso aqui NO hace falta replicar manualmente los "if" que crean el
# wrapper solo si hay contenido -- basta con construir el dict completo
# (con None en los campos ausentes, que dict_to_xml tambien omite como
# atributo) y dejar que el mecanismo de poda automatica haga el resto.
# =====================================================================

def _get_horas_extra_items(items: list[dict]) -> list[dict]:
    """Equivalente dict de _add_horas_extra(). items = lista de horas extra
    de un tipo (HEDs/HENs/etc, cada item con Cantidad/Porcentaje/Pago/
    HoraInicio/HoraFin)."""
    result = []
    for item in items:
        node = {
            'Cantidad': str(item.get('Cantidad', '0')),
            'Porcentaje': _fmt(item.get('Porcentaje', 0)),
            'Pago': _fmt(item.get('Pago', 0)),
        }
        if item.get('HoraInicio'):
            node['HoraInicio'] = item['HoraInicio']
        if item.get('HoraFin'):
            node['HoraFin'] = item['HoraFin']
        result.append(node)
    return result


def _get_transporte_items(transporte) -> list[dict]:
    """Equivalente dict del bloque Transporte de _add_devengados().

    AUD-DIAN-34 (2026-10-04): ver nota equivalente en _add_devengados()
    -- ViaticoManuAlojS/NS se omiten (None, que dict_to_xml descarta)
    cuando el valor es 0; evidencia empírica real contra la DIAN hoy
    contradice la premisa anterior de incluirlos siempre en "0.00"
    (causaba NIE072/073).
    """
    if not transporte:
        return []
    if isinstance(transporte, dict):
        transporte = [transporte]
    items = []
    for t in transporte:
        viatico_s = float(t.get('ViaticoManuAlojS') or 0)
        viatico_ns = float(t.get('ViaticoManuAlojNS') or 0)
        if (
            t.get('AuxilioTransporte') is None
            and viatico_s <= 0
            and viatico_ns <= 0
        ):
            continue
        items.append({
            'AuxilioTransporte': (
                _fmt(t['AuxilioTransporte'])
                if t.get('AuxilioTransporte') is not None else None
            ),
            'ViaticoManuAlojS': _fmt(viatico_s) if viatico_s > 0 else None,
            'ViaticoManuAlojNS': _fmt(viatico_ns) if viatico_ns > 0 else None,
        })
    return items


def _get_vacaciones_node(vac_data: dict) -> dict:
    """Equivalente dict del bloque Vacaciones de _add_devengados()."""
    if not vac_data:
        return {}
    comunes = []
    for vc in vac_data.get('VacacionesComunes', []):
        node = {
            'Cantidad': str(vc.get('Cantidad', '0')),
            'Pago': _fmt(vc.get('Pago', 0)),
        }
        if vc.get('FechaInicio'):
            node['FechaInicio'] = vc['FechaInicio']
        if vc.get('FechaFin'):
            node['FechaFin'] = vc['FechaFin']
        comunes.append(node)

    compensadas = [
        {
            'Cantidad': str(vcomp.get('Cantidad', '0')),
            'Pago': _fmt(vcomp.get('Pago', 0)),
        }
        for vcomp in vac_data.get('VacacionesCompensadas', [])
    ]

    return {
        'VacacionesComunes': comunes,
        'VacacionesCompensadas': compensadas,
    }


def _get_primas_node(primas: dict) -> dict:
    """Equivalente dict del bloque Primas de _add_devengados()."""
    if not primas:
        return {}
    node = {
        'Cantidad': str(primas.get('Cantidad', '0')),
        'Pago': _fmt(primas.get('Pago', 0)),
    }
    if primas.get('PagoNS') is not None:
        node['PagoNS'] = _fmt(primas['PagoNS'])
    return node


def _get_cesantias_node(ces: dict) -> dict:
    """Equivalente dict del bloque Cesantias de _add_devengados()."""
    if not ces:
        return {}
    return {
        'Pago': _fmt(ces.get('Pago', 0)),
        'Porcentaje': _fmt(ces.get('Porcentaje', 0)),
        'PagoIntereses': _fmt(ces.get('PagoIntereses', 0)),
    }


def _get_incapacidades_items(incap_list: list[dict]) -> list[dict]:
    """Equivalente dict del bloque Incapacidades de _add_devengados()."""
    result = []
    for inc in incap_list:
        node = {
            'Cantidad': str(inc.get('Cantidad', '0')),
            'Tipo': str(inc.get('Tipo', '1')),
            'Pago': _fmt(inc.get('Pago', 0)),
        }
        if inc.get('FechaInicio'):
            node['FechaInicio'] = inc['FechaInicio']
        if inc.get('FechaFin'):
            node['FechaFin'] = inc['FechaFin']
        result.append(node)
    return result


def _get_licencias_node(lic_data: dict) -> dict:
    """Equivalente dict del bloque Licencias de _add_devengados()."""
    if not lic_data:
        return {}

    def _con_fechas(items, campos_extra=()):
        result = []
        for it in items:
            node = {'Cantidad': str(it.get('Cantidad', '0'))}
            for campo in campos_extra:
                node[campo] = _fmt(it.get(campo, 0))
            if it.get('FechaInicio'):
                node['FechaInicio'] = it['FechaInicio']
            if it.get('FechaFin'):
                node['FechaFin'] = it['FechaFin']
            result.append(node)
        return result

    return {
        'LicenciaMP': _con_fechas(lic_data.get('LicenciaMP', []), ('Pago',)),
        'LicenciaR': _con_fechas(lic_data.get('LicenciaR', []), ('Pago',)),
        'LicenciaNR': _con_fechas(lic_data.get('LicenciaNR', [])),
    }


def _get_bonificaciones_items(bonif_list: list[dict]) -> list[dict]:
    """Equivalente dict del bloque Bonificaciones de _add_devengados()."""
    result = []
    for b in bonif_list:
        result.append({
            'BonificacionS': (
                _fmt(b['BonificacionS']) if b.get('BonificacionS') is not None else None
            ),
            'BonificacionNS': (
                _fmt(b['BonificacionNS']) if b.get('BonificacionNS') is not None else None
            ),
        })
    return result


def _get_auxilios_items(aux_list: list[dict]) -> list[dict]:
    """Equivalente dict del bloque Auxilios de _add_devengados()."""
    result = []
    for a in aux_list:
        result.append({
            'AuxilioS': _fmt(a['AuxilioS']) if a.get('AuxilioS') is not None else None,
            'AuxilioNS': _fmt(a['AuxilioNS']) if a.get('AuxilioNS') is not None else None,
        })
    return result


def _get_huelgas_legales_items(huelgas: list[dict]) -> list[dict]:
    """Equivalente dict del bloque HuelgasLegales de _add_devengados()."""
    result = []
    for h in huelgas:
        node = {'Cantidad': str(h.get('Cantidad', '0'))}
        if h.get('FechaInicio'):
            node['FechaInicio'] = h['FechaInicio']
        if h.get('FechaFin'):
            node['FechaFin'] = h['FechaFin']
        result.append(node)
    return result


def _get_otros_conceptos_items(otros: list[dict]) -> list[dict]:
    """Equivalente dict del bloque OtrosConceptos de _add_devengados()."""
    result = []
    for o in otros:
        result.append({
            'DescripcionConcepto': o.get('DescripcionConcepto', ''),
            'ConceptoS': _fmt(o['ConceptoS']) if o.get('ConceptoS') is not None else None,
            'ConceptoNS': _fmt(o['ConceptoNS']) if o.get('ConceptoNS') is not None else None,
        })
    return result


def _get_compensaciones_items(comp_list: list[dict]) -> list[dict]:
    """Equivalente dict del bloque Compensaciones de _add_devengados()."""
    return [
        {
            'CompensacionO': _fmt(c.get('CompensacionO', 0)),
            'CompensacionE': _fmt(c.get('CompensacionE', 0)),
        }
        for c in comp_list
    ]


def _get_bono_epctv_items(bonos: list[dict]) -> list[dict]:
    """Equivalente dict del bloque BonoEPCTVs de _add_devengados()."""
    result = []
    for bn in bonos:
        result.append({
            'PagoS': _fmt(bn['PagoS']) if bn.get('PagoS') is not None else None,
            'PagoNS': _fmt(bn['PagoNS']) if bn.get('PagoNS') is not None else None,
            'PagoAlimentacionS': (
                _fmt(bn['PagoAlimentacionS'])
                if bn.get('PagoAlimentacionS') is not None else None
            ),
            'PagoAlimentacionNS': (
                _fmt(bn['PagoAlimentacionNS'])
                if bn.get('PagoAlimentacionNS') is not None else None
            ),
        })
    return result


def _get_valor_simple_items(valores: list) -> list[dict]:
    """Equivalente dict de los bloques Comisiones/PagosTerceros/Anticipos/
    OtrasDeducciones de _add_devengados()/_add_deducciones() -- listas de
    valores simples, cada uno un elemento con solo texto (_fmt)."""
    return [{'_text': _fmt(v)} for v in valores]


def _get_devengados_node(data: dict) -> dict:
    """Equivalente dict de _add_devengados(). data = sub-dict 'devengados'."""
    basico = data.get('Basico', {})
    node = {
        'Basico': {
            'DiasTrabajados': str(basico.get('DiasTrabajados', '30')),
            'SueldoTrabajado': _fmt(basico.get('SueldoTrabajado', 0)),
        },
        'Transporte': _get_transporte_items(data.get('Transporte')),
        'HEDs': {'HED': _get_horas_extra_items(data.get('HEDs', []))},
        'HENs': {'HEN': _get_horas_extra_items(data.get('HENs', []))},
        'HRNs': {'HRN': _get_horas_extra_items(data.get('HRNs', []))},
        'HEDDFs': {'HEDDF': _get_horas_extra_items(data.get('HEDDFs', []))},
        'HRDDFs': {'HRDDF': _get_horas_extra_items(data.get('HRDDFs', []))},
        'HENDFs': {'HENDF': _get_horas_extra_items(data.get('HENDFs', []))},
        'HRNDFs': {'HRNDF': _get_horas_extra_items(data.get('HRNDFs', []))},
        'Vacaciones': _get_vacaciones_node(data.get('Vacaciones')),
        'Primas': _get_primas_node(data.get('Primas')),
        'Cesantias': _get_cesantias_node(data.get('Cesantias')),
        'Incapacidades': {
            'Incapacidad': _get_incapacidades_items(data.get('Incapacidades', [])),
        },
        'Licencias': _get_licencias_node(data.get('Licencias')),
        'Bonificaciones': {
            'Bonificacion': _get_bonificaciones_items(data.get('Bonificaciones', [])),
        },
        'Auxilios': {'Auxilio': _get_auxilios_items(data.get('Auxilios', []))},
        'HuelgasLegales': {
            'HuelgaLegal': _get_huelgas_legales_items(data.get('HuelgasLegales', [])),
        },
        'OtrosConceptos': {
            'OtroConcepto': _get_otros_conceptos_items(data.get('OtrosConceptos', [])),
        },
        'Compensaciones': {
            'Compensacion': _get_compensaciones_items(data.get('Compensaciones', [])),
        },
        'BonoEPCTVs': {
            'BonoEPCTV': _get_bono_epctv_items(data.get('BonoEPCTVs', [])),
        },
        'Comisiones': {
            'Comision': _get_valor_simple_items(data.get('Comisiones', [])),
        },
        'PagosTerceros': {
            'PagoTercero': _get_valor_simple_items(data.get('PagosTerceros', [])),
        },
        'Anticipos': {
            'Anticipo': _get_valor_simple_items(data.get('Anticipos', [])),
        },
    }

    for campo in ('Dotacion', 'ApoyoSost', 'Teletrabajo',
                  'BonifRetiro', 'Indemnizacion', 'Reintegro'):
        val = data.get(campo)
        if val is not None:
            node[campo] = {'_text': _fmt(val)}

    return node


def _get_deducciones_node(data: dict) -> dict:
    """Equivalente dict de _add_deducciones(). data = sub-dict 'deducciones'."""
    salud = data.get('Salud', {})
    pension = data.get('FondoPension', {})
    fsp = data.get('FondoSP') or {}

    node = {
        'Salud': {
            'Porcentaje': _fmt(salud.get('Porcentaje', 4)),
            'Deduccion': _fmt(salud.get('Deduccion', 0)),
        },
        'FondoPension': {
            'Porcentaje': _fmt(pension.get('Porcentaje', 4)),
            'Deduccion': _fmt(pension.get('Deduccion', 0)),
        },
        'FondoSP': {
            'Porcentaje': _fmt(fsp['Porcentaje']) if fsp.get('Porcentaje') is not None else None,
            'DeduccionSP': (
                _fmt(fsp['DeduccionSP']) if fsp.get('DeduccionSP') is not None else None
            ),
            'PorcentajeSub': (
                _fmt(fsp['PorcentajeSub']) if fsp.get('PorcentajeSub') is not None else None
            ),
            'DeduccionSub': (
                _fmt(fsp['DeduccionSub']) if fsp.get('DeduccionSub') is not None else None
            ),
        },
        'Sindicatos': {
            'Sindicato': [
                {
                    'Porcentaje': _fmt(s.get('Porcentaje', 0)),
                    'Deduccion': _fmt(s.get('Deduccion', 0)),
                }
                for s in data.get('Sindicatos', [])
            ],
        },
        'Sanciones': {
            'Sancion': [
                {
                    'SancionPublic': _fmt(s.get('SancionPublic', 0)),
                    'SancionPriv': _fmt(s.get('SancionPriv', 0)),
                }
                for s in data.get('Sanciones', [])
            ],
        },
        'Libranzas': {
            'Libranza': [
                {
                    'Descripcion': l.get('Descripcion', ''),
                    'Deduccion': _fmt(l.get('Deduccion', 0)),
                }
                for l in data.get('Libranzas', [])
            ],
        },
        'PagosTerceros': {
            'PagoTercero': _get_valor_simple_items(data.get('PagosTerceros', [])),
        },
        'Anticipos': {
            'Anticipo': _get_valor_simple_items(data.get('Anticipos', [])),
        },
        'OtrasDeducciones': {
            'OtraDeduccion': _get_valor_simple_items(data.get('OtrasDeducciones', [])),
        },
    }

    for campo in ('PensionVoluntaria', 'RetencionFuente', 'AFC',
                  'Cooperativa', 'EmbargoFiscal', 'PlanComplementarios',
                  'Educacion', 'Reintegro', 'Deuda'):
        val = data.get(campo)
        if val is not None:
            node[campo] = {'_text': _fmt(val)}

    return node


# Template parcial -- SOLO las 9 secciones simples de esta fase, en el
# mismo orden en que build_nomina_individual() las agrega hoy (pasos
# 3-13 salvo CodigoQR/Notas, que son valores simples sin sub-estructura
# y no necesitan node-builder propio). Uso exclusivo del harness de
# comparación de abajo -- NO es el template completo del documento
# (ese se arma en la Fase 2, cuando Devengados/Deducciones también
# tengan su propio _get_X_node()).
_TEMPLATE_SECCIONES_SIMPLES = {
    'Periodo': {},
    'NumeroSecuenciaXML': {},
    'LugarGeneracionXML': {},
    'ProveedorXML': {},
    'InformacionGeneral': {},
    'Empleador': {},
    'Trabajador': {},
    'Pago': {},
    'FechasPagos': {'FechaPago': {}},
}


def _build_secciones_simples_node(data: dict) -> dict:
    """Arma el fragmento de las 9 secciones simples como un solo dict.

    Uso exclusivo del harness de comparación Fase 1 -- compone las 9
    secciones bajo un tag contenedor ficticio para poder renderizarlas
    con dict_to_xml() de forma aislada, sin necesitar todavía el
    documento NominaIndividual completo (que requiere Devengados/
    Deducciones, Fase 2).
    """
    return {
        '_tag': 'SeccionesSimplesTest',
        'Periodo': _get_periodo_node(data.get('periodo', {})),
        'NumeroSecuenciaXML': _get_numero_secuencia_node(
            data.get('numero_secuencia', {})),
        'LugarGeneracionXML': _get_lugar_generacion_node(
            data.get('lugar_generacion', {})),
        'ProveedorXML': _get_proveedor_xml_node(data.get('proveedor_xml', {})),
        'InformacionGeneral': _get_informacion_general_node(
            data.get('informacion_general', {})),
        'Empleador': _get_empleador_node(data.get('empleador', {})),
        'Trabajador': _get_trabajador_node(data.get('trabajador', {})),
        'Pago': _get_pago_node(data.get('pago', {})),
        'FechasPagos': _get_fechas_pagos_node(data.get('fechas_pagos', [])),
    }


# =====================================================================
# Orquestador real (doc 24 SS8, paso 1, cerrado al final por orden de
# riesgo) -- build_nomina_individual_v2()/build_nota_ajuste_v2().
#
# TODAVIA NO CONECTADO AL FLUJO REAL: hr_payslip.py sigue llamando a
# build_nomina_individual()/build_nota_ajuste() (las funciones viejas,
# sin tocar). Este bloque es codigo nuevo en paralelo, pendiente de que
# Tech Lead de luz verde al corte tras revisar la verificacion XSD+C14N
# del DOCUMENTO COMPLETO (no solo de las secciones sueltas de las Fases
# 1/2), ver doc 24 SS13.
#
# Decision de diseno: CodigoQR y ext:UBLExtensions NO se arman via
# dict_to_xml aunque tengan una funcion _get_X_node equivalente en las
# fases anteriores -- son elementos "placeholder", requeridos por el
# XSD pero legitimamente vacios en la primera pasada (CUNE/QR se
# calculan e insertan DESPUES via re-parseo, ver doc 24 SS6; la firma
# digital se inserta en UBLExtensions todavia mas tarde). dict_to_xml
# omite automaticamente cualquier elemento sin atributos/texto/hijos
# (la poda automatica que simplifico Devengados/Deducciones en la Fase
# 2) -- exactamente el comportamiento CORRECTO para secciones opcionales
# de verdad, pero INCORRECTO aqui: silenciaria <CodigoQR></CodigoQR> y
# <ext:UBLExtensions></ext:UBLExtensions> en la primera pasada, dejando
# esos 2 elementos requeridos (minOccurs=1) sin generar, y el
# post-procesamiento de CUNE/firma no tendria donde insertar el valor
# despues. Por eso se mantienen con los helpers viejos _el()/
# _add_ubl_extensions() sin cambios (mismo criterio que Notas/Redondeo/
# los 3 totales, que tampoco tienen esa ambiguedad -- _fmt(0) nunca es
# '', y Notas/Redondeo ya son opcionales de verdad, se omiten a
# proposito cuando no hay dato).
# =====================================================================

def _append_dict_section(parent: etree._Element, tag: str, node: dict, nsmap: dict) -> None:
    """Renderiza `node` con dict_to_xml() bajo `tag` y lo agrega a `parent`
    en el namespace por defecto de `nsmap` -- o no agrega nada si
    dict_to_xml() poda el nodo por estar vacio (mismo criterio ya
    verificado en Fases 1/2)."""
    node = dict(node)
    node['_tag'] = tag
    element = dict_to_xml(node, nsmap=nsmap)
    if element is not None:
        parent.append(element)


def build_nomina_individual_v2(data: dict) -> bytes:
    """Equivalente a build_nomina_individual(), migrado a dict_to_xml()
    para las secciones estructuradas (Fases 1 y 2). Ver nota de diseno
    arriba sobre por que UBLExtensions/CodigoQR/Notas/Redondeo/totales
    siguen usando los helpers viejos _el()/_attr()/_add_ubl_extensions().

    NO esta conectada al flujo real todavia -- ver doc 24 SS13."""
    root = etree.Element('{%s}NominaIndividual' % NS_NOMINA, nsmap=_NSMAP_NOMINA)
    root.set('SchemaLocation', '')
    root.set('{%s}schemaLocation' % NS_XSD,
             '%s NominaIndividualElectronicaXSD.xsd' % NS_NOMINA)

    _add_ubl_extensions(root)

    novedad = data.get('novedad')
    if novedad:
        _el(root, 'Novedad', text=str(novedad.get('value', 'false')).lower(),
            CUNENov=novedad.get('CUNENov', ''))

    _append_dict_section(root, 'Periodo', _get_periodo_node(data.get('periodo', {})), _NSMAP_NOMINA)
    _append_dict_section(root, 'NumeroSecuenciaXML',
                          _get_numero_secuencia_node(data.get('numero_secuencia', {})), _NSMAP_NOMINA)
    _append_dict_section(root, 'LugarGeneracionXML',
                          _get_lugar_generacion_node(data.get('lugar_generacion', {})), _NSMAP_NOMINA)
    _append_dict_section(root, 'ProveedorXML',
                          _get_proveedor_xml_node(data.get('proveedor_xml', {})), _NSMAP_NOMINA)

    _el(root, 'CodigoQR', text=data.get('codigo_qr', ''))

    _append_dict_section(root, 'InformacionGeneral',
                          _get_informacion_general_node(data.get('informacion_general', {})), _NSMAP_NOMINA)

    notas = data.get('notas')
    if notas:
        if isinstance(notas, str):
            notas = [notas]
        for nota in notas:
            _el(root, 'Notas', text=nota)

    _append_dict_section(root, 'Empleador', _get_empleador_node(data.get('empleador', {})), _NSMAP_NOMINA)
    _append_dict_section(root, 'Trabajador', _get_trabajador_node(data.get('trabajador', {})), _NSMAP_NOMINA)
    _append_dict_section(root, 'Pago', _get_pago_node(data.get('pago', {})), _NSMAP_NOMINA)
    _append_dict_section(root, 'FechasPagos',
                          _get_fechas_pagos_node(data.get('fechas_pagos', [])), _NSMAP_NOMINA)
    _append_dict_section(root, 'Devengados', _get_devengados_node(data.get('devengados', {})), _NSMAP_NOMINA)
    _append_dict_section(root, 'Deducciones', _get_deducciones_node(data.get('deducciones', {})), _NSMAP_NOMINA)

    if data.get('redondeo') is not None:
        _el(root, 'Redondeo', text=_fmt(data['redondeo']))

    _el(root, 'DevengadosTotal', text=_fmt(data.get('devengados_total', 0)))
    _el(root, 'DeduccionesTotal', text=_fmt(data.get('deducciones_total', 0)))
    _el(root, 'ComprobanteTotal', text=_fmt(data.get('comprobante_total', 0)))

    return _serialize(root)


def _build_reemplazar_v2(parent: etree._Element, data: dict) -> None:
    """Equivalente a _build_reemplazar(), migrado -- ver build_nomina_individual_v2()."""
    remp = _el(parent, 'Reemplazar')

    pred = data.get('predecesor', {})
    _attr(remp, 'ReemplazandoPredecesor',
          NumeroPred=str(pred.get('NumeroPred', '')),
          CUNEPred=str(pred.get('CUNEPred', '')),
          FechaGenPred=str(pred.get('FechaGenPred', '')))

    _append_dict_section(remp, 'Periodo', _get_periodo_node(data.get('periodo', {})), _NSMAP_AJUSTE)
    _append_dict_section(remp, 'NumeroSecuenciaXML',
                          _get_numero_secuencia_node(data.get('numero_secuencia', {})), _NSMAP_AJUSTE)
    _append_dict_section(remp, 'LugarGeneracionXML',
                          _get_lugar_generacion_node(data.get('lugar_generacion', {})), _NSMAP_AJUSTE)
    _append_dict_section(remp, 'ProveedorXML',
                          _get_proveedor_xml_node(data.get('proveedor_xml', {})), _NSMAP_AJUSTE)

    _el(remp, 'CodigoQR', text=data.get('codigo_qr', ''))

    _append_dict_section(remp, 'InformacionGeneral',
                          _get_informacion_general_node(data.get('informacion_general', {})), _NSMAP_AJUSTE)

    notas = data.get('notas')
    if notas:
        if isinstance(notas, str):
            notas = [notas]
        for nota in notas:
            _el(remp, 'Notas', text=nota)

    _append_dict_section(remp, 'Empleador', _get_empleador_node(data.get('empleador', {})), _NSMAP_AJUSTE)
    _append_dict_section(remp, 'Trabajador', _get_trabajador_node(data.get('trabajador', {})), _NSMAP_AJUSTE)
    _append_dict_section(remp, 'Pago', _get_pago_node(data.get('pago', {})), _NSMAP_AJUSTE)
    _append_dict_section(remp, 'FechasPagos',
                          _get_fechas_pagos_node(data.get('fechas_pagos', [])), _NSMAP_AJUSTE)
    _append_dict_section(remp, 'Devengados', _get_devengados_node(data.get('devengados', {})), _NSMAP_AJUSTE)
    _append_dict_section(remp, 'Deducciones', _get_deducciones_node(data.get('deducciones', {})), _NSMAP_AJUSTE)

    if data.get('redondeo') is not None:
        _el(remp, 'Redondeo', text=_fmt(data['redondeo']))

    _el(remp, 'DevengadosTotal', text=_fmt(data.get('devengados_total', 0)))
    _el(remp, 'DeduccionesTotal', text=_fmt(data.get('deducciones_total', 0)))
    _el(remp, 'ComprobanteTotal', text=_fmt(data.get('comprobante_total', 0)))


def _build_eliminar_v2(parent: etree._Element, data: dict) -> None:
    """Equivalente a _build_eliminar(), migrado -- ver build_nomina_individual_v2().

    Nota (doc 31): hereda tal cual el bug preexistente de atributos invalidos
    contra el XSD de Ajuste (CodigoTrabajador/PeriodoNomina) -- no se corrige
    aqui, doc 24 migra la construccion del XML, no corrige bugs normativos
    independientes encontrados en el camino."""
    elim = _el(parent, 'Eliminar')

    pred = data.get('predecesor', {})
    _attr(elim, 'EliminandoPredecesor',
          NumeroPred=str(pred.get('NumeroPred', '')),
          CUNEPred=str(pred.get('CUNEPred', '')),
          FechaGenPred=str(pred.get('FechaGenPred', '')))

    _append_dict_section(elim, 'NumeroSecuenciaXML',
                          _get_numero_secuencia_node(data.get('numero_secuencia', {})), _NSMAP_AJUSTE)
    _append_dict_section(elim, 'LugarGeneracionXML',
                          _get_lugar_generacion_node(data.get('lugar_generacion', {})), _NSMAP_AJUSTE)
    _append_dict_section(elim, 'ProveedorXML',
                          _get_proveedor_xml_node(data.get('proveedor_xml', {})), _NSMAP_AJUSTE)

    _el(elim, 'CodigoQR', text=data.get('codigo_qr', ''))

    _append_dict_section(elim, 'InformacionGeneral',
                          _get_informacion_general_node(data.get('informacion_general', {})), _NSMAP_AJUSTE)

    notas = data.get('notas')
    if notas:
        if isinstance(notas, str):
            notas = [notas]
        for nota in notas:
            _el(elim, 'Notas', text=nota)

    _append_dict_section(elim, 'Empleador', _get_empleador_node(data.get('empleador', {})), _NSMAP_AJUSTE)


def build_nota_ajuste_v2(data: dict) -> bytes:
    """Equivalente a build_nota_ajuste(), migrado -- ver build_nomina_individual_v2().

    NO esta conectada al flujo real todavia -- ver doc 24 SS13."""
    root = etree.Element('{%s}NominaIndividualDeAjuste' % NS_NOMINA_AJUSTE, nsmap=_NSMAP_AJUSTE)
    root.set('SchemaLocation', '')
    root.set('{%s}schemaLocation' % NS_XSD,
             '%s NominaIndividualDeAjusteElectronicaXSD.xsd' % NS_NOMINA_AJUSTE)

    _add_ubl_extensions(root)
    _el(root, 'TipoNota', text=str(data.get('tipo_nota', '1')))

    reemplazar = data.get('reemplazar')
    if reemplazar:
        _build_reemplazar_v2(root, reemplazar)

    eliminar = data.get('eliminar')
    if eliminar:
        _build_eliminar_v2(root, eliminar)

    return _serialize(root)
