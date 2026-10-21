# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Generador de archivo plano PILA v2 — Registro Tipo 1 + Tipo 2.

Implementa la generación completa del archivo plano PILA con:
- Registro Tipo 01: Encabezado del aportante (datos de la empresa)
- Registro Tipo 02: Detalle por cotizante (un registro por empleado)

Formato: campos separados por pipe ``|``, codificación UTF-8, finales CRLF.

Referencia: Resolución 2388 de 2016 y modificaciones posteriores
(Resolución 5858 de 2016, Resolución 3016 de 2017).

Todas las funciones son puras — sin dependencias de Odoo.
"""

import logging
import unicodedata
from typing import Union

_logger = logging.getLogger(__name__)

# =====================================================================
# Constantes
# =====================================================================

# Separador de campos PILA
PIPE = '|'

# Final de línea PILA
LINE_ENDING = '\r\n'


# =====================================================================
# Normalización de texto
# =====================================================================

def _normalize_text(text: str) -> str:
    """Elimina acentos/tildes y convierte a mayúsculas.

    Reemplaza caracteres acentuados por su equivalente ASCII
    (ñ→N, á→A, é→E, etc.) y convierte todo a mayúsculas.

    Args:
        text: Texto de entrada.

    Returns:
        Texto normalizado en mayúsculas sin acentos ni tildes.
    """
    if not text:
        return ''
    # Reemplazar ñ/Ñ antes de la descomposición Unicode
    text = text.replace('ñ', 'n').replace('Ñ', 'N')
    # Descomponer caracteres Unicode y eliminar marcas diacríticas
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_text = ''.join(
        c for c in nfkd if not unicodedata.combining(c)
    )
    return ascii_text.upper()


# =====================================================================
# Formateo de campos
# =====================================================================

def _fmt_text(value: Union[str, None]) -> str:
    """Formatea campo de texto: normalizado, sin acentos, mayúsculas."""
    if value is None:
        return ''
    return _normalize_text(str(value))


def _fmt_str(value: Union[str, int, float, None]) -> str:
    """Convierte cualquier valor a string de forma segura."""
    if value is None:
        return ''
    return str(value)


def _fmt_int(value: Union[int, float, str, None]) -> str:
    """Formatea un valor entero sin decimales."""
    if value is None or value == '':
        return '0'
    return str(int(float(value)))


def _fmt_amount(value: Union[int, float, str, None], decimals: int = 0) -> str:
    """Formatea un monto numérico.

    Args:
        value: Valor numérico.
        decimals: Número de decimales (0 para enteros).

    Returns:
        String numérico formateado.
    """
    if value is None or value == '':
        return '0' if decimals == 0 else f'0.{"0" * decimals}'
    if decimals == 0:
        return str(int(round(float(value))))
    return f'{float(value):.{decimals}f}'


def _fmt_rate(value: Union[float, str, None]) -> str:
    """Formatea una tarifa con 5 decimales (ej: 0.16000)."""
    if value is None or value == '':
        return ''
    return f'{float(value):.5f}'


def _fmt_date(value: Union[str, None]) -> str:
    """Formatea fecha YYYY-MM-DD o vacío."""
    if not value:
        return ''
    return str(value).strip()[:10]


# =====================================================================
# Registro Tipo 01 — Encabezado del aportante
# =====================================================================

# Definición de campos del Tipo 01 en orden según Resolución 2388
_TIPO_01_FIELDS = [
    # (nombre_campo, tipo_formato)
    ('tipo_registro', 'str'),               # 01 = Encabezado
    ('modalidad_planilla', 'str'),           # 1=unica, 2=acumulada
    ('secuencia', 'str'),                    # 0001
    ('razon_social', 'text'),               # Nombre del aportante
    ('tipo_documento_aportante', 'str'),    # NI=NIT, CC, CE
    ('numero_documento_aportante', 'str'),  # Sin DV
    ('digito_verificacion', 'str'),         # DV del NIT
    ('tipo_planilla', 'str'),               # E, Y, A, S, N, etc.
    ('numero_planilla_asociada', 'str'),    # Para correcciones
    ('fecha_pago_asociada', 'date'),        # YYYY-MM-DD (correcciones)
    ('forma_presentacion', 'str'),          # U=unica, S=sucursal
    ('codigo_sucursal', 'str'),             # Código de la sucursal
    ('nombre_sucursal', 'text'),            # Nombre de la sucursal
    ('codigo_arl', 'str'),                  # Código ARL
    ('periodo_cotizacion_salud', 'str'),    # YYYY-MM
    ('periodo_cotizacion_pension', 'str'),  # YYYY-MM
    ('numero_total_cotizantes', 'int'),     # Total empleados
    ('valor_total_nomina', 'amount'),       # Valor total nómina
    ('tipo_aportante', 'str'),              # 1-8
    ('codigo_operador', 'str'),             # Código operador PILA
    ('fecha_pago', 'date'),                 # YYYY-MM-DD
    ('numero_planilla', 'str'),             # Número de planilla
]


def generate_tipo_01(data: dict) -> str:
    """Genera el registro Tipo 01 (encabezado del aportante).

    El registro Tipo 01 contiene la información general del aportante
    (empresa), los períodos de cotización y los totales de la planilla.
    Debe existir exactamente un registro Tipo 01 por archivo.

    Args:
        data: Diccionario con las claves correspondientes a los campos
              del registro Tipo 01.

    Returns:
        Línea de texto con campos separados por pipe.

    Examples:
        >>> data = {
        ...     'tipo_registro': '01', 'modalidad_planilla': '1',
        ...     'secuencia': '0001', 'razon_social': 'InSoTech SAS',
        ...     'tipo_documento_aportante': 'NI',
        ...     'numero_documento_aportante': '901797249',
        ...     'digito_verificacion': '5', 'tipo_planilla': 'E',
        ...     'numero_total_cotizantes': 10,
        ...     'valor_total_nomina': 25000000.00,
        ... }
        >>> line = generate_tipo_01(data)
        >>> line.startswith('01|')
        True
    """
    campos = []

    for field_name, field_type in _TIPO_01_FIELDS:
        value = data.get(field_name)

        if field_type == 'str':
            campos.append(_fmt_str(value))
        elif field_type == 'text':
            campos.append(_fmt_text(value))
        elif field_type == 'int':
            campos.append(_fmt_int(value))
        elif field_type == 'amount':
            campos.append(_fmt_amount(value, decimals=0))
        elif field_type == 'date':
            campos.append(_fmt_date(value))
        else:
            campos.append(_fmt_str(value))

    return PIPE.join(campos)


# =====================================================================
# Registro Tipo 02 — Detalle de cotizante
# =====================================================================

# Definición completa de los campos del Tipo 02 según Resolución 2388.
# Cada tupla: (nombre_campo, tipo_formato)
_TIPO_02_FIELDS = [
    # --- Identificación del cotizante (campos 1-14) ---
    ('tipo_registro', 'str'),            # 02 = Detalle
    ('secuencia', 'str'),                # 00001, 00002, etc.
    ('tipo_documento', 'str'),           # CC, CE, PA, TI, CD, RC
    ('numero_documento', 'str'),         # Número de identificación
    ('tipo_cotizante', 'str'),           # 01=dependiente, 02=doméstico...
    ('subtipo_cotizante', 'str'),        # 00=no aplica
    ('extranjero_no_pension', 'str'),    # X=si, espacio=no
    ('colombiano_exterior', 'str'),      # X=si, espacio=no
    ('codigo_departamento', 'str'),      # Código DANE departamento
    ('codigo_municipio', 'str'),         # Código DANE municipio
    ('primer_apellido', 'name'),         # Normalizado mayúsculas
    ('segundo_apellido', 'name'),        # Normalizado mayúsculas
    ('primer_nombre', 'name'),           # Normalizado mayúsculas
    ('segundo_nombre', 'name'),          # Normalizado mayúsculas

    # --- Novedades (campos 15-30) ---
    ('nov_ing', 'str'),                  # Ingreso: X o vacío
    ('nov_ret', 'str'),                  # Retiro: X o vacío
    ('nov_tde', 'str'),                  # Traslado desde otra EPS
    ('nov_tae', 'str'),                  # Traslado a otra EPS
    ('nov_tdp', 'str'),                  # Traslado desde otra AFP
    ('nov_tap', 'str'),                  # Traslado a otra AFP
    ('nov_vsp', 'str'),                  # Variación permanente salario
    ('nov_correcciones', 'str'),         # Corrección (linea)
    ('nov_vst', 'str'),                  # Variación transitoria salario
    ('nov_sln', 'str'),                  # Suspensión temporal / licencia no remunerada
    ('nov_ige', 'str'),                  # Incapacidad general
    ('nov_lma', 'str'),                  # Licencia de maternidad
    ('nov_vac', 'str'),                  # Vacaciones / licencia remunerada
    ('nov_avp', 'str'),                  # Aporte voluntario pensión
    ('nov_vct', 'str'),                  # Variación centros de trabajo
    ('nov_irl', 'str'),                  # IRL (incapacidad riesgo laboral)

    # --- Códigos administradoras (campos 31-35) ---
    ('codigo_afp', 'str'),              # Código fondo de pensiones
    ('codigo_afp_traslado', 'str'),     # AFP destino traslado
    ('codigo_eps', 'str'),              # Código EPS
    ('codigo_eps_traslado', 'str'),     # EPS destino traslado
    ('codigo_ccf', 'str'),             # Código caja compensación

    # --- Días cotizados (campos 36-39) ---
    ('dias_pension', 'int'),            # Días cotizados pensión
    ('dias_salud', 'int'),              # Días cotizados salud
    ('dias_arl', 'int'),                # Días cotizados ARL
    ('dias_ccf', 'int'),                # Días cotizados CCF

    # --- Salario (campos 40-41) ---
    ('salario_basico', 'amount'),        # Salario base mensual
    ('salario_integral', 'str'),         # X=integral, vacío=no

    # --- IBC por subsistema (campos 42-45) ---
    ('ibc_pension', 'amount'),           # IBC pensión
    ('ibc_salud', 'amount'),             # IBC salud
    ('ibc_arl', 'amount'),              # IBC ARL
    ('ibc_ccf', 'amount'),              # IBC CCF

    # --- Pensión (campos 46-53) ---
    ('tarifa_pension', 'rate'),          # Tarifa AFP (ej: 0.16000)
    ('cotizacion_pension', 'amount'),    # Aporte obligatorio pensión
    ('avp_afiliado', 'amount'),          # Aporte voluntario pensión afiliado
    ('avp_aportante', 'amount'),         # Aporte voluntario pensión empleador
    ('total_cotizacion_pension', 'amount'),  # Total AFP
    ('aporte_fsp_subcuenta', 'amount'),  # Fondo de Solidaridad Pensional - subcuenta solidaridad
    ('aporte_fsp_subsistencia', 'amount'),  # FSP - subcuenta subsistencia
    ('valor_no_retenido', 'amount'),     # Valor no retenido

    # --- Salud (campos 54-60) ---
    ('tarifa_salud', 'rate'),            # Tarifa EPS (ej: 0.12500)
    ('cotizacion_salud', 'amount'),      # Aporte salud
    ('valor_upc', 'amount'),             # Valor UPC adicional
    ('numero_autorizacion_ige', 'str'),  # Número autorización incapacidad
    ('valor_incapacidad_ige', 'amount'), # Valor incapacidad general
    ('numero_autorizacion_lma', 'str'),  # Número autorización maternidad
    ('valor_licencia_lma', 'amount'),    # Valor licencia maternidad

    # --- ARL (campos 61-63) ---
    ('tarifa_arl', 'rate'),              # Tarifa ARL según riesgo
    ('centro_trabajo', 'str'),           # Código centro de trabajo ARL
    ('cotizacion_arl', 'amount'),        # Aporte ARL

    # --- Parafiscales (campos 64-73) ---
    ('tarifa_ccf', 'rate'),              # Tarifa CCF (0.04000)
    ('aporte_ccf', 'amount'),            # Aporte CCF
    ('tarifa_sena', 'rate'),             # Tarifa SENA (0.02000)
    ('aporte_sena', 'amount'),           # Aporte SENA
    ('tarifa_icbf', 'rate'),             # Tarifa ICBF (0.03000)
    ('aporte_icbf', 'amount'),           # Aporte ICBF
    ('tarifa_esap', 'rate'),             # Tarifa ESAP
    ('aporte_esap', 'amount'),           # Aporte ESAP
    ('tarifa_men', 'rate'),              # Tarifa MEN
    ('aporte_men', 'amount'),            # Aporte MEN

    # --- UPC adicional / Exoneración (campos 74-76) ---
    ('tipo_documento_upc', 'str'),       # Tipo doc beneficiario UPC
    ('numero_documento_upc', 'str'),     # Número doc beneficiario UPC
    ('exonerado_parafiscales', 'str'),   # S=exonerado, N=no

    # --- ARL detalle (campos 77-79) ---
    ('codigo_arl', 'str'),               # Código ARL
    ('clase_riesgo', 'str'),             # 1-5
    ('tarifa_especial_pension', 'str'),  # Indicador tarifa especial AFP

    # --- Fechas de novedades (campos 80-94) ---
    ('fecha_ingreso', 'date'),           # Fecha ingreso
    ('fecha_retiro', 'date'),            # Fecha retiro
    ('fecha_inicio_vsp', 'date'),        # Inicio variación permanente
    ('fecha_inicio_sln', 'date'),        # Inicio suspensión/licencia NR
    ('fecha_fin_sln', 'date'),           # Fin suspensión/licencia NR
    ('fecha_inicio_ige', 'date'),        # Inicio incapacidad general
    ('fecha_fin_ige', 'date'),           # Fin incapacidad general
    ('fecha_inicio_lma', 'date'),        # Inicio licencia maternidad
    ('fecha_fin_lma', 'date'),           # Fin licencia maternidad
    ('fecha_inicio_vac', 'date'),        # Inicio vacaciones/LR
    ('fecha_fin_vac', 'date'),           # Fin vacaciones/LR
    ('fecha_inicio_vct', 'date'),        # Inicio variación centro trabajo
    ('fecha_fin_vct', 'date'),           # Fin variación centro trabajo
    ('fecha_inicio_irl', 'date'),        # Inicio incapacidad riesgo laboral
    ('fecha_fin_irl', 'date'),           # Fin incapacidad riesgo laboral

    # --- Campos finales (campos 95-98) ---
    ('ibc_otros_parafiscales', 'amount'),  # IBC otros parafiscales
    ('horas_laboradas', 'int'),           # Número horas laboradas
    ('fecha_radicacion_exterior', 'date'),  # Fecha radicación exterior
    ('actividad_economica_arl', 'str'),  # Código actividad económica ARL
]


def generate_tipo_02(data: dict) -> str:
    """Genera un registro Tipo 02 (detalle de cotizante).

    Un registro Tipo 02 corresponde a un empleado/cotizante individual
    y contiene todos sus datos de identificación, novedades, días
    cotizados, IBC, tarifas y aportes a cada subsistema.

    Args:
        data: Diccionario con las claves correspondientes a los 98
              campos del registro Tipo 02.

    Returns:
        Línea de texto con campos separados por pipe.

    Examples:
        >>> data = {
        ...     'tipo_registro': '02', 'secuencia': '00001',
        ...     'tipo_documento': 'CC', 'numero_documento': '123456789',
        ...     'tipo_cotizante': '01', 'subtipo_cotizante': '00',
        ...     'primer_apellido': 'Garcia', 'primer_nombre': 'Juan',
        ... }
        >>> line = generate_tipo_02(data)
        >>> line.startswith('02|')
        True
    """
    campos = []

    for field_name, field_type in _TIPO_02_FIELDS:
        value = data.get(field_name)

        if field_type == 'str':
            campos.append(_fmt_str(value))
        elif field_type == 'name':
            campos.append(_fmt_text(value))
        elif field_type == 'int':
            campos.append(_fmt_int(value))
        elif field_type == 'amount':
            campos.append(_fmt_amount(value, decimals=0))
        elif field_type == 'rate':
            campos.append(_fmt_rate(value))
        elif field_type == 'date':
            campos.append(_fmt_date(value))
        else:
            campos.append(_fmt_str(value))

    return PIPE.join(campos)


# =====================================================================
# Función principal — Generación del archivo PILA completo (v2)
# =====================================================================

def generate_pila_file_v2(
    aportante: dict,
    cotizantes: list[dict],
) -> str:
    """Genera el contenido completo del archivo plano PILA v2.

    Genera un archivo con:
        1. Un registro Tipo 01 (encabezado del aportante).
        2. N registros Tipo 02 (detalle por cotizante).

    Args:
        aportante: Diccionario con datos del aportante para Tipo 01.
        cotizantes: Lista de diccionarios con datos de cotizantes
                    para registros Tipo 02.

    Returns:
        Contenido completo del archivo PILA como string UTF-8,
        con separador pipe y finales de línea CRLF.

    Examples:
        >>> aportante = {'tipo_registro': '01', 'razon_social': 'Test'}
        >>> cotizantes = [{'tipo_registro': '02', 'secuencia': '00001'}]
        >>> content = generate_pila_file_v2(aportante, cotizantes)
        >>> '01|' in content
        True
    """
    lines = []

    # Tipo 01 — Encabezado del aportante
    _logger.info(
        'Generando registro Tipo 01 para aportante: %s',
        aportante.get('razon_social', ''),
    )
    lines.append(generate_tipo_01(aportante))

    # Tipo 02 — Detalle de cotizantes
    _logger.info(
        'Generando %d registros Tipo 02',
        len(cotizantes),
    )
    for cotizante in cotizantes:
        lines.append(generate_tipo_02(cotizante))

    return LINE_ENDING.join(lines) + LINE_ENDING


# =====================================================================
# Resumen / Validación del archivo
# =====================================================================

def compute_summary(cotizantes: list[dict]) -> dict:
    """Calcula un resumen de totales desde la lista de cotizantes.

    Útil para mostrar un resumen al usuario antes de generar el archivo.

    Args:
        cotizantes: Lista de diccionarios (datos Tipo 02).

    Returns:
        Diccionario con totales:
        - total_cotizantes: int
        - total_ibc_pension: float
        - total_ibc_salud: float
        - total_ibc_arl: float
        - total_ibc_ccf: float
        - total_aporte_pension: float
        - total_aporte_salud: float
        - total_aporte_arl: float
        - total_aporte_ccf: float
        - total_aporte_sena: float
        - total_aporte_icbf: float
        - total_general: float
    """
    resumen = {
        'total_cotizantes': len(cotizantes),
        'total_ibc_pension': 0.0,
        'total_ibc_salud': 0.0,
        'total_ibc_arl': 0.0,
        'total_ibc_ccf': 0.0,
        'total_aporte_pension': 0.0,
        'total_aporte_salud': 0.0,
        'total_aporte_arl': 0.0,
        'total_aporte_ccf': 0.0,
        'total_aporte_sena': 0.0,
        'total_aporte_icbf': 0.0,
        'total_general': 0.0,
    }

    for cot in cotizantes:
        resumen['total_ibc_pension'] += float(cot.get('ibc_pension') or 0)
        resumen['total_ibc_salud'] += float(cot.get('ibc_salud') or 0)
        resumen['total_ibc_arl'] += float(cot.get('ibc_arl') or 0)
        resumen['total_ibc_ccf'] += float(cot.get('ibc_ccf') or 0)
        resumen['total_aporte_pension'] += float(
            cot.get('cotizacion_pension') or 0)
        resumen['total_aporte_salud'] += float(
            cot.get('cotizacion_salud') or 0)
        resumen['total_aporte_arl'] += float(
            cot.get('cotizacion_arl') or 0)
        resumen['total_aporte_ccf'] += float(cot.get('aporte_ccf') or 0)
        resumen['total_aporte_sena'] += float(cot.get('aporte_sena') or 0)
        resumen['total_aporte_icbf'] += float(cot.get('aporte_icbf') or 0)

    resumen['total_general'] = (
        resumen['total_aporte_pension']
        + resumen['total_aporte_salud']
        + resumen['total_aporte_arl']
        + resumen['total_aporte_ccf']
        + resumen['total_aporte_sena']
        + resumen['total_aporte_icbf']
    )

    return resumen
