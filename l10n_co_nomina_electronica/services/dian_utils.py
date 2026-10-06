"""Utilidades DIAN Colombia — Nómina Electrónica.

Funciones puras (sin dependencias de Odoo) para cálculos y
transformaciones requeridas por la DIAN colombiana en el contexto
de nómina electrónica.

Adaptado de insotech_core/utils/dian.py eliminando funciones que
dependen de modelos Odoo (partner_to_dian_dict, get_partner_doc_type).
"""

import logging
import math
import re
from datetime import date as _date_type
from typing import Optional, Union

from . import cune as _cune_module

_logger = logging.getLogger(__name__)


# =====================================================================
# Dígito de Verificación (DV) — Resolución DIAN
# =====================================================================

def compute_dv(nit_str: Union[str, int]) -> str:
    """Calcula dígito de verificación DIAN para un NIT colombiano.

    Algoritmo oficial de la DIAN basado en factores primos.

    Args:
        nit_str: NIT como string o entero (solo dígitos, sin DV).

    Returns:
        Dígito de verificación ('0' a '9').

    Examples:
        >>> compute_dv('901797249')
        '5'
    """
    factors = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    nit_str = str(nit_str).zfill(15)[-15:]  # Truncar a 15 dígitos máximo
    total = 0
    for i, digit in enumerate(reversed(nit_str)):
        total += int(digit) * factors[i]
    remainder = total % 11
    return str(11 - remainder) if remainder >= 2 else str(remainder)


# =====================================================================
# Limpieza de NIT
# =====================================================================

def clean_nit(vat_str: str, strip_dv: bool = True) -> str:
    """Extrae solo dígitos del NIT, opcionalmente sin DV.

    La DIAN espera el NIT sin DV en la mayoría de campos XML.
    Odoo almacena el VAT como NIT+DV concatenados (ej: '9017972495').

    Args:
        vat_str: VAT como viene del sistema (puede tener guiones, DV, etc.).
        strip_dv: Si True y tiene 10 dígitos, quita el último (DV).

    Returns:
        NIT limpio (solo dígitos, sin DV).
    """
    if not vat_str:
        return ''
    digits = re.sub(r'[^0-9]', '', str(vat_str))
    # NIT+DV son 10 dígitos — quitar DV
    if strip_dv and len(digits) == 10:
        digits = digits[:9]
    return digits


# =====================================================================
# Tipo de Documento DIAN
# =====================================================================

# Mapeo de códigos Odoo l10n_co → códigos numéricos DIAN
DOC_TYPE_MAP: dict[str, str] = {
    'rut': '31',                    # NIT
    'id_card': '13',                # Cédula de Ciudadanía
    'national_citizen_id': '13',    # Cédula de Ciudadanía (Odoo 19)
    'id_document': '13',            # Cédula genérica
    'passport': '41',               # Pasaporte
    'foreign_id_card': '22',        # Cédula de Extranjería
    'foreign_id': '22',             # Alias
    'external_id': '42',            # Documento de identificación extranjero
    'civil_registration': '11',     # Registro Civil
    'niup': '91',                   # NUIP
}


def get_doc_type_code(l10n_co_document_code: str) -> str:
    """Convierte un código de documento Odoo al código numérico DIAN.

    Args:
        l10n_co_document_code: Código de tipo de documento de Odoo
                               (ej: 'rut', 'national_citizen_id').

    Returns:
        Código numérico DIAN (ej: '31', '13').
    """
    if not l10n_co_document_code:
        return '13'  # Default: Cédula
    code = str(l10n_co_document_code).lower().strip()
    return DOC_TYPE_MAP.get(code, code)


# =====================================================================
# Formateo de montos para CUNE
# =====================================================================

def format_amount(value: Union[int, float, str]) -> str:
    """Formatea un valor numérico a string con 2 decimales truncados.

    El cálculo del CUNE requiere que los montos se representen con
    exactamente 2 decimales *truncados* (no redondeados) según el
    Anexo Técnico DIAN.

    Args:
        value: Valor numérico (int, float o string numérico).

    Returns:
        String con 2 decimales truncados (ej: '1500000.00').

    Examples:
        >>> format_amount(1500000)
        '1500000.00'
        >>> format_amount('25000.5')
        '25000.50'
        >>> format_amount('25000.999')
        '25000.99'
    """
    return '%.2f' % (math.trunc(float(value) * 100) / 100)


# =====================================================================
# URLs de la DIAN por ambiente — único punto (AUD-DIAN-34, 2026-10-05)
# =====================================================================
# Antes repetidas en 3 sitios (aquí mismo, sin usar -- get_nomina_wsdl_url()
# nunca tuvo caller; services/soap_client.py con sus propias constantes
# DIAN_ENDPOINT_HAB/PROD; models/hr_payslip.py con el host del QR escrito
# aparte). Los valores son los que ya estaban hardcodeados -- esta
# consolidación no cambia ninguno. soap_client.py y hr_payslip.py ahora
# llaman a get_soap_endpoint()/get_qr_catalog_host() en vez de mantener su
# propia copia. El parámetro ``override`` (opcional) es para quien sí tiene
# acceso a Odoo (dian_utils es puro, sin ORM): lee el ir.config_parameter
# correspondiente y lo pasa aquí -- ver ResCompany._ne_dian_endpoint()/
# _ne_dian_qr_host() en models/res_company.py.

DIAN_URLS = {
    '1': {  # Producción
        'soap': 'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc',
        'qr_host': 'catalogo-vpfe.dian.gov.co',
    },
    '2': {  # Habilitación / Pruebas
        'soap': 'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc',
        'qr_host': 'catalogo-vpfe-hab.dian.gov.co',
    },
}


def get_soap_endpoint(environment: str, override: Optional[str] = None) -> str:
    """Retorna la URL del servicio SOAP de la DIAN según el ambiente.

    Args:
        environment: Código de ambiente DIAN: '1' → Producción, '2' → Habilitación/Pruebas.
        override: Valor ya leído de ir.config_parameter, si lo hay (gana sobre el default).

    Returns:
        URL completa del servicio SOAP.

    Examples:
        >>> get_soap_endpoint('1')
        'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc'
        >>> get_soap_endpoint('2')
        'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc'
    """
    if override:
        return override
    return DIAN_URLS.get(str(environment), DIAN_URLS['2'])['soap']


def get_qr_catalog_host(environment: str, override: Optional[str] = None) -> str:
    """Retorna el host del catálogo DIAN usado para construir la URL del CodigoQR.

    Args:
        environment: Código de ambiente DIAN: '1' → Producción, '2' → Habilitación/Pruebas.
        override: Valor ya leído de ir.config_parameter, si lo hay (gana sobre el default).

    Returns:
        Host (sin esquema) del catálogo DIAN.

    Examples:
        >>> get_qr_catalog_host('1')
        'catalogo-vpfe.dian.gov.co'
        >>> get_qr_catalog_host('2')
        'catalogo-vpfe-hab.dian.gov.co'
    """
    if override:
        return override
    return DIAN_URLS.get(str(environment), DIAN_URLS['2'])['qr_host']


# =====================================================================
# Validación de parámetros enteros configurables (timeouts)
# =====================================================================

def parse_positive_int(raw_value, default: int, param_name: str = '') -> int:
    """Valida un valor leído de ir.config_parameter como entero positivo.

    Usado para los timeouts configurables del módulo (SOAP_TIMEOUT, tick/timeout del
    motor de habilitación): una configuración mal escrita nunca debe reventar un envío
    a la DIAN -- se usa el valor por defecto y se deja un ``_logger.warning``.

    Args:
        raw_value: Valor crudo (string, o lo que devuelva ir.config_parameter.get_param()).
        default: Valor a usar si raw_value es None/vacío/no es un entero positivo.
        param_name: Nombre del parámetro, solo para el mensaje de warning.

    Returns:
        El entero validado, o ``default``.

    Examples:
        >>> parse_positive_int('30', 45, 'x')
        30
        >>> parse_positive_int('abc', 45, 'x')
        45
        >>> parse_positive_int(None, 45, 'x')
        45
        >>> parse_positive_int('-5', 45, 'x')
        45
    """
    if raw_value is not None and str(raw_value).strip():
        try:
            value = int(str(raw_value).strip())
        except ValueError:
            value = None
        if value is not None and value > 0:
            return value
        _logger.warning(
            "Parámetro '%s'='%s' inválido (se esperaba un entero positivo); "
            "usando el valor por defecto %s.", param_name, raw_value, default,
        )
    return default


# =====================================================================
# Período de Nómina DIAN
# =====================================================================

def get_periodo_nomina(date_from, date_to) -> str:
    """Determina el código de período de nómina según la DIAN.

    Los códigos de período están definidos en el Anexo Técnico:
        1 = Semanal   (≤ 7 días)
        2 = Decenal   (≤ 10 días)
        3 = Catorcenal (≤ 14 días)
        4 = Quincenal  (15–16 días)
        5 = Mensual    (28–31 días)
        6 = Otro

    Args:
        date_from: Fecha inicio del período (date o str 'YYYY-MM-DD').
        date_to:   Fecha fin del período (date o str 'YYYY-MM-DD').

    Returns:
        Código de período como string ('1' a '6').

    Examples:
        >>> from datetime import date
        >>> get_periodo_nomina(date(2024, 1, 1), date(2024, 1, 7))
        '1'
        >>> get_periodo_nomina('2024-01-01', '2024-01-31')
        '5'
    """
    if isinstance(date_from, str):
        date_from = _date_type.fromisoformat(date_from)
    if isinstance(date_to, str):
        date_to = _date_type.fromisoformat(date_to)

    delta_days = (date_to - date_from).days + 1  # inclusivo

    if delta_days <= 7:
        return '1'   # Semanal
    if delta_days <= 10:
        return '2'   # Decenal
    if delta_days <= 14:
        return '3'   # Catorcenal
    if delta_days <= 16:
        return '4'   # Quincenal
    if 28 <= delta_days <= 31:
        return '5'   # Mensual
    return '6'        # Otro


# =====================================================================
# Códigos geográficos DANE
# =====================================================================

def get_department_code(state_record) -> str:
    """Extrae el código de departamento DANE desde un res.country.state.

    Utiliza ``l10n_co_edi_code`` (primeros 2 dígitos) si está disponible,
    de lo contrario usa el campo ``code``.

    Args:
        state_record: Recordset de res.country.state o None.

    Returns:
        Código de departamento como string (ej: '11' para Bogotá).
    """
    if not state_record:
        return ''
    edi_code = getattr(state_record, 'l10n_co_edi_code', None)
    if edi_code:
        # AUD-DIAN-34 (2026-09-14): l10n_co_edi_code es Integer nativo de
        # Odoo -- pierde el cero a la izquierda (Antioquia = 5, no '05').
        # La tabla 5.4.2 del Anexo Tecnico exige 2 digitos exactos
        # (reglas NIE014/NIE036/NIE051); sin zfill, la DIAN rechaza el
        # codigo como invalido aunque el valor en si sea correcto.
        return str(edi_code)[:2].zfill(2)
    code = getattr(state_record, 'code', None)
    return str(code) if code else ''


def get_city_code(city_record) -> str:
    """Extrae el código de municipio DANE desde un res.city.

    Utiliza ``l10n_co_edi_code`` si existe, de lo contrario
    intenta con ``zipcode``.

    Args:
        city_record: Recordset de res.city o None.

    Returns:
        Código DANE del municipio (ej: '11001' para Bogotá).
    """
    if not city_record:
        return ''
    edi_code = getattr(city_record, 'l10n_co_edi_code', None)
    if edi_code:
        # AUD-DIAN-34 (2026-09-14): mismo problema que get_department_code
        # -- Integer nativo sin cero a la izquierda (Itagui = 5360, no
        # '05360'). Tabla 5.4.3 exige 5 digitos (departamento + 3 del
        # municipio) exactos (reglas NIE015/NIE037/NIE052).
        return str(edi_code).zfill(5)
    zipcode = getattr(city_record, 'zipcode', None)
    return str(zipcode) if zipcode else ''


# =====================================================================
# Separación de nombre en formato colombiano
# =====================================================================

def split_name(full_name: str) -> dict:
    """Separa un nombre completo en componentes colombianos.

    La convención colombiana ordena los nombres como:
        PrimerNombre [SegundoNombre] PrimerApellido [SegundoApellido]

    Args:
        full_name: Nombre completo (ej: 'Juan Carlos García López').

    Returns:
        Diccionario con las claves:
        - ``primer_nombre``
        - ``otros_nombres``
        - ``primer_apellido``
        - ``segundo_apellido``

    Examples:
        >>> split_name('Juan Carlos García López')
        {'primer_nombre': 'Juan', 'otros_nombres': 'Carlos', \
'primer_apellido': 'García', 'segundo_apellido': 'López'}
        >>> split_name('María Rodríguez')
        {'primer_nombre': 'María', 'otros_nombres': '', \
'primer_apellido': 'Rodríguez', 'segundo_apellido': ''}
    """
    result = {
        'primer_nombre': '',
        'otros_nombres': '',
        'primer_apellido': '',
        'segundo_apellido': '',
    }
    if not full_name or not full_name.strip():
        return result

    parts = full_name.strip().split()
    length = len(parts)

    if length == 1:
        result['primer_nombre'] = parts[0]
    elif length == 2:
        result['primer_nombre'] = parts[0]
        result['primer_apellido'] = parts[1]
    elif length == 3:
        result['primer_nombre'] = parts[0]
        result['primer_apellido'] = parts[1]
        result['segundo_apellido'] = parts[2]
    else:  # 4 o más palabras
        result['primer_nombre'] = parts[0]
        result['otros_nombres'] = ' '.join(parts[1:-2])
        result['primer_apellido'] = parts[-2]
        result['segundo_apellido'] = parts[-1]

    return result


# =====================================================================
# Cálculo de días trabajados
# =====================================================================

def compute_worked_time(date_start, date_end) -> int:
    """Calcula el número de días entre dos fechas.

    Args:
        date_start: Fecha inicio (date o str 'YYYY-MM-DD').
        date_end:   Fecha fin (date o str 'YYYY-MM-DD').

    Returns:
        Número de días como entero. Retorna 0 si alguna fecha es None.

    Examples:
        >>> from datetime import date
        >>> compute_worked_time(date(2024, 1, 1), date(2024, 1, 31))
        30
        >>> compute_worked_time('2024-01-01', '2024-01-15')
        14
    """
    if not date_start or not date_end:
        return 0
    if isinstance(date_start, str):
        date_start = _date_type.fromisoformat(date_start)
    if isinstance(date_end, str):
        date_end = _date_type.fromisoformat(date_end)
    return (date_end - date_start).days


# =====================================================================
# Código de seguridad del software (wrapper)
# =====================================================================

def compute_software_security_code(
    software_id: str,
    pin: str,
    doc_number: str,
) -> str:
    """Calcula el código de seguridad del software (SoftwareSC).

    Wrapper de conveniencia sobre :func:`cune.compute_software_security_code`
    para que los módulos consumidores solo necesiten importar ``dian_utils``.

    Args:
        software_id: Identificador del software asignado por la DIAN.
        pin:         PIN del software asignado por la DIAN.
        doc_number:  Número del documento de nómina electrónica.

    Returns:
        Hash SHA-384 en hexadecimal (96 caracteres).
    """
    return _cune_module.compute_software_security_code(
        software_id, pin, doc_number,
    )
