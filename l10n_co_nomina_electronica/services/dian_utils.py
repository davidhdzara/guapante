"""Utilidades DIAN Colombia — Nómina Electrónica.

Funciones puras (sin dependencias de Odoo) para cálculos y
transformaciones requeridas por la DIAN colombiana en el contexto
de nómina electrónica.

Adaptado de insotech_core/utils/dian.py eliminando funciones que
dependen de modelos Odoo (partner_to_dian_dict, get_partner_doc_type).
"""

import logging
import re
from datetime import date as _date_type
from typing import Optional, Union

from . import cune as _cune_module
from .montos import format_amount  # noqa: F401 -- se publica también desde aquí

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


# Longitud del código DANE de un municipio: departamento + municipio (Tabla 5.4.3 del Anexo Técnico DIAN; DIVIPOLA del DANE). La parte del
# departamento mide lo que mida el código del propio departamento: no hay un «2» ni un «3» escritos en la partición (H-F4-08).
DANE_MUNICIPIO_LONGITUD = 5


def get_pila_municipality_code(department_code, city_dane_code) -> str:
    """Campo 10 del registro tipo 2 de PILA (código del municipio de ubicación laboral): la parte del MUNICIPIO dentro de su
    departamento (H-F4-08, doc 99 §2; Anexo Técnico 2 de la Res. 2388/2016, campos 9 y 10).

    El campo 9 lleva el departamento y el 10 solo el resto del código DANE de la ciudad (``11001`` -> departamento ``11``, municipio
    ``001``). NO se usa ``get_city_code`` para esto: cae a ``zipcode`` cuando la ciudad no tiene código DANE y un código postal no es
    DIVIPOLA. Aquí el código DANE se EXIGE, y el municipio solo se acepta si empieza por el código de su departamento.

    Args:
        department_code: código de 2 dígitos del departamento (``get_department_code``), o '' si no hay.
        city_dane_code: ``l10n_co_edi_code`` de la ciudad (entero sin el cero a la izquierda, o texto), o falsy si no hay.

    Returns:
        La parte del municipio (3 dígitos con el código de 5 y el departamento de 2).

    Raises:
        ValueError: el único argumento es el MOTIVO, para que quien llama arme el mensaje con el empleado y la ciudad:
            ``departamento_sin_codigo`` (vacío o no numérico, p. ej. el código alfabético de Odoo), ``ciudad_sin_codigo``,
            ``ciudad_codigo_invalido`` (no es numérico o es más largo que un código DANE) o ``ciudad_otro_departamento``
            (el código de la ciudad no empieza por el del departamento: dato inconsistente).
    """
    departamento = str(department_code or '').strip()
    if not departamento.isdigit() or len(departamento) >= DANE_MUNICIPIO_LONGITUD:
        raise ValueError('departamento_sin_codigo')
    crudo = str(city_dane_code or '').strip()
    if not crudo:
        raise ValueError('ciudad_sin_codigo')
    dane = crudo.zfill(DANE_MUNICIPIO_LONGITUD)
    if not dane.isdigit() or len(dane) != DANE_MUNICIPIO_LONGITUD:
        raise ValueError('ciudad_codigo_invalido')
    if not dane.startswith(departamento):
        raise ValueError('ciudad_otro_departamento')
    return dane[len(departamento):]


# =====================================================================
# Separación de nombre en formato colombiano
# =====================================================================

def split_name(full_name: str, particulas=()) -> dict:
    """Prellena nombres y apellidos colombianos SOLO cuando no hay ambigüedad.

    La convención es ``PrimerNombre [OtrosNombres] PrimerApellido [SegundoApellido]``,
    pero a partir de un único texto no se puede saber dónde termina el nombre
    (``Juan Carlos Pérez`` vs. ``Juan Pérez Gómez``) ni dónde empiezan los apellidos
    compuestos (``de la Cruz``). Por eso se prellena únicamente:

    - 1 palabra: primer nombre;
    - 2 palabras: primer nombre + primer apellido;
    - 4 palabras sin partículas: nombre, otro nombre, primer y segundo apellido.

    Cualquier otro caso (3 palabras, 5 o más, o con alguna de ``particulas``: de, del,
    la...) devuelve todo vacío: lo completa una persona, nunca se adivina.

    Args:
        full_name: Nombre completo.
        particulas: palabras (minúsculas) que vuelven ambiguo un nombre; salen de un
            parámetro del sistema, no del código.

    Returns:
        dict con ``primer_nombre``, ``otros_nombres``, ``primer_apellido``,
        ``segundo_apellido``.
    """
    result = {
        'primer_nombre': '',
        'otros_nombres': '',
        'primer_apellido': '',
        'segundo_apellido': '',
    }
    parts = (full_name or '').split()
    if not parts:
        return result
    if any(part.lower() in particulas for part in parts):
        return result
    if len(parts) == 1:
        result['primer_nombre'] = parts[0]
    elif len(parts) == 2:
        result['primer_nombre'], result['primer_apellido'] = parts
    elif len(parts) == 4:
        (result['primer_nombre'], result['otros_nombres'],
         result['primer_apellido'], result['segundo_apellido']) = parts
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


def compute_worked_time_360(date_start, date_end, *, inclusive) -> int:
    """TiempoLaborado según el Anexo Técnico de Nómina Electrónica §8.3.1 (p. 249).

    Convención 1 año = 360 días y 1 mes = 30 días, MISMA del mes comercial que usa la
    nómina (HrPayslip._ne_dia_comercial): el último día real de cada mes (28/29-feb, 30 o
    31) vale 30 y ningún día pasa de 30. Cuenta = años*360 + meses*30 + días comerciales.
    Mínimo 1 (regla NIE006: valor >= 1).

    USO PREVISTO: ``inclusive=True``. Decisión de David (D19, 2026-11-11): el día de
    ingreso SÍ cuenta (el empleado no pierde ni un día), igual que ``_ne_dias_bajo_contrato``
    (ingreso el 10 de un mes de 31 días: 10..30 = 21 días). ``inclusive`` sigue siendo
    obligatorio, sin valor por defecto.

    NO está conectada al XML todavía: ``compute_worked_time`` (días calendario) sigue en
    uso hasta cerrar D3/D6/D10/D14 (doc 53 §21.1).

    Args:
        date_start: Fecha de ingreso (date o 'YYYY-MM-DD').
        date_end:   Fecha final del periodo (date o 'YYYY-MM-DD').
        inclusive:  True cuenta ambos extremos; False no cuenta el día de ingreso.

    Returns:
        Entero >= 1. Retorna 0 si alguna fecha es None.

    Examples:
        >>> from datetime import date
        >>> compute_worked_time_360(date(2018, 1, 1), date(2023, 4, 18), inclusive=True)
        1908
    """
    import calendar

    if not date_start or not date_end:
        return 0
    if isinstance(date_start, str):
        date_start = _date_type.fromisoformat(date_start)
    if isinstance(date_end, str):
        date_end = _date_type.fromisoformat(date_end)

    def comercial(d):
        ultimo = calendar.monthrange(d.year, d.month)[1]
        return 30 if d.day == ultimo else min(d.day, 30)

    dias = ((date_end.year - date_start.year) * 360
            + (date_end.month - date_start.month) * 30
            + comercial(date_end) - comercial(date_start))
    if inclusive:
        dias += 1
    return max(1, dias)


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
