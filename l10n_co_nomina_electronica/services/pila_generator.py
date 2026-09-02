"""Generador de archivo plano PILA — Planilla Integrada de Liquidación de Aportes.

Implementa la generación del archivo plano TXT con separador pipe ``|``
según las especificaciones de la Resolución 2388 de 2016 y sus
modificaciones posteriores.

El archivo PILA contiene los siguientes tipos de registro:
    - Tipo 1: Encabezado del aportante
    - Tipo 2: Detalle por cotizante (un registro por empleado)
    - Tipo 8: Totales por administradora de pensiones (AFP)
    - Tipo 9: Totales por administradora de salud (EPS)
    - Tipo 10: Totales por administradora de riesgos laborales (ARL)
    - Tipo 11: Totales por caja de compensación familiar (CCF)
    - Tipo 12: Totales generales de la planilla

Todas las funciones son puras — sin efectos secundarios ni
dependencias de Odoo.
"""

import unicodedata
from collections import defaultdict
from typing import Union


# =====================================================================
# Normalización de texto
# =====================================================================

def normalize_text(text: str) -> str:
    """Elimina acentos/tildes y convierte a mayúsculas.

    Reemplaza caracteres acentuados por su equivalente ASCII
    (ñ→N, á→A, é→E, etc.) y convierte todo a mayúsculas.

    Args:
        text: Texto de entrada en cualquier formato.

    Returns:
        Texto normalizado en mayúsculas sin acentos ni tildes.

    Examples:
        >>> normalize_text('María García')
        'MARIA GARCIA'
        >>> normalize_text('Peñaranda')
        'PENARANDA'
        >>> normalize_text('José Andrés')
        'JOSE ANDRES'
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

def _fmt_amount(value: Union[int, float, str, None], decimals: int = 2) -> str:
    """Formatea un valor numérico para el archivo PILA.

    Args:
        value: Valor numérico (int, float o string numérico).
               Si es None o vacío, retorna '0' para enteros o
               '0.00' para decimales.
        decimals: Número de decimales a mostrar. Usar 0 para enteros.

    Returns:
        String formateado sin separador de miles y con ``.`` decimal.

    Examples:
        >>> _fmt_amount(1500000.50)
        '1500000.50'
        >>> _fmt_amount(30, decimals=0)
        '30'
        >>> _fmt_amount(None)
        '0.00'
    """
    if value is None or value == '':
        return '0' if decimals == 0 else f'0.{"0" * decimals}'
    if decimals == 0:
        return str(int(float(value)))
    return f'{float(value):.{decimals}f}'


def _fmt_text(value: Union[str, None]) -> str:
    """Formatea un campo de texto para el archivo PILA.

    Args:
        value: Texto de entrada o None.

    Returns:
        Texto normalizado (mayúsculas, sin acentos) o cadena vacía.

    Examples:
        >>> _fmt_text('García')
        'GARCIA'
        >>> _fmt_text(None)
        ''
    """
    if value is None:
        return ''
    return normalize_text(str(value))


def _fmt_date(value: Union[str, None]) -> str:
    """Formatea un campo de fecha para el archivo PILA.

    Args:
        value: Fecha en formato YYYY-MM-DD o None.

    Returns:
        Fecha formateada o cadena vacía.

    Examples:
        >>> _fmt_date('2024-01-15')
        '2024-01-15'
        >>> _fmt_date(None)
        ''
    """
    if not value:
        return ''
    return str(value).strip()


def _safe_str(value: Union[str, int, float, None]) -> str:
    """Convierte cualquier valor a string de forma segura.

    Args:
        value: Valor de cualquier tipo o None.

    Returns:
        Representación string del valor, o cadena vacía si es None.

    Examples:
        >>> _safe_str(42)
        '42'
        >>> _safe_str(None)
        ''
    """
    if value is None:
        return ''
    return str(value)


# =====================================================================
# Registro Tipo 1 — Encabezado del aportante
# =====================================================================

def generate_tipo_1(data: dict) -> str:
    """Genera el registro Tipo 1 (encabezado del aportante).

    El registro Tipo 1 contiene la información general del aportante
    y los totales de la planilla. Debe existir exactamente un registro
    Tipo 1 por archivo.

    Args:
        data: Diccionario con las siguientes claves:
            - tipo_registro: str = '1'
            - modalidad: str (1=normal)
            - secuencia: str = '1'
            - razon_social: str
            - tipo_documento: str (NI, CC, CE, etc.)
            - numero_documento: str
            - digito_verificacion: str
            - tipo_planilla: str (E=empleados, I=independientes, etc.)
            - num_planilla_asociada: str (opcional)
            - fecha_pago_asociada: str (opcional, YYYY-MM-DD)
            - forma_presentacion: str (U=unico, S=sucursal)
            - codigo_sucursal: str (opcional)
            - nombre_sucursal: str (opcional)
            - codigo_arl: str
            - periodo_pago_otros: str (YYYY-MM)
            - periodo_pago_salud: str (YYYY-MM)
            - numero_planilla: str
            - fecha_pago: str (YYYY-MM-DD, opcional)
            - total_cotizantes: int
            - valor_total_nomina: float
            - tipo_aportante: str (1-8)
            - codigo_operador: str

    Returns:
        Línea de texto con 22 campos separados por pipe ``|``.

    Examples:
        >>> data = {
        ...     'tipo_registro': '1', 'modalidad': '1', 'secuencia': '1',
        ...     'razon_social': 'InSoTech SAS', 'tipo_documento': 'NI',
        ...     'numero_documento': '901797249',
        ...     'digito_verificacion': '5', 'tipo_planilla': 'E',
        ...     'num_planilla_asociada': '', 'fecha_pago_asociada': '',
        ...     'forma_presentacion': 'U', 'codigo_sucursal': '',
        ...     'nombre_sucursal': '', 'codigo_arl': '14-23',
        ...     'periodo_pago_otros': '2024-01',
        ...     'periodo_pago_salud': '2024-01',
        ...     'numero_planilla': '0001', 'fecha_pago': '2024-02-05',
        ...     'total_cotizantes': 10, 'valor_total_nomina': 25000000.00,
        ...     'tipo_aportante': '1', 'codigo_operador': '01',
        ... }
        >>> line = generate_tipo_1(data)
        >>> line.startswith('1|')
        True
    """
    fields = [
        _safe_str(data.get('tipo_registro', '1')),
        _safe_str(data.get('modalidad', '1')),
        _safe_str(data.get('secuencia', '1')),
        _fmt_text(data.get('razon_social', '')),
        _safe_str(data.get('tipo_documento', '')),
        _safe_str(data.get('numero_documento', '')),
        _safe_str(data.get('digito_verificacion', '')),
        _safe_str(data.get('tipo_planilla', '')),
        _safe_str(data.get('num_planilla_asociada', '')),
        _fmt_date(data.get('fecha_pago_asociada', '')),
        _safe_str(data.get('forma_presentacion', '')),
        _safe_str(data.get('codigo_sucursal', '')),
        _fmt_text(data.get('nombre_sucursal', '')),
        _safe_str(data.get('codigo_arl', '')),
        _safe_str(data.get('periodo_pago_otros', '')),
        _safe_str(data.get('periodo_pago_salud', '')),
        _safe_str(data.get('numero_planilla', '')),
        _fmt_date(data.get('fecha_pago', '')),
        _fmt_amount(data.get('total_cotizantes'), decimals=0),
        _fmt_amount(data.get('valor_total_nomina'), decimals=2),
        _safe_str(data.get('tipo_aportante', '')),
        _safe_str(data.get('codigo_operador', '')),
    ]
    return '|'.join(fields)


# =====================================================================
# Registro Tipo 2 — Detalle de cotizante
# =====================================================================

# Orden exacto de los 98 campos del registro Tipo 2 según el Anexo
# Técnico de la Resolución 2388 de 2016.
_TIPO_2_FIELD_ORDER: list[tuple[str, str]] = [
    # Identificación (campos 1-14)
    ('tipo_registro', 'text'),
    ('secuencia', 'text'),
    ('tipo_documento', 'text'),
    ('numero_documento', 'text'),
    ('tipo_cotizante', 'text'),
    ('subtipo_cotizante', 'text'),
    ('extranjero', 'text'),
    ('colombiano_exterior', 'text'),
    ('departamento', 'text'),
    ('municipio', 'text'),
    ('primer_apellido', 'name'),
    ('segundo_apellido', 'name'),
    ('primer_nombre', 'name'),
    ('segundo_nombre', 'name'),

    # Novedades (campos 15-30) — marcadores X o vacío
    ('ing', 'text'),
    ('ret', 'text'),
    ('tde', 'text'),
    ('tae', 'text'),
    ('tdp', 'text'),
    ('tap', 'text'),
    ('vsp', 'text'),
    ('linea', 'text'),
    ('vst', 'text'),
    ('sln', 'text'),
    ('ige', 'text'),
    ('lma', 'text'),
    ('vac_lr', 'text'),
    ('avp', 'text'),
    ('vct', 'text'),
    ('irl', 'text'),

    # Códigos de administradoras (campos 31-35)
    ('afp', 'text'),
    ('afp_traslado', 'text'),
    ('eps', 'text'),
    ('eps_traslado', 'text'),
    ('ccf', 'text'),

    # Días cotizados (campos 36-39)
    ('dias_afp', 'int'),
    ('dias_eps', 'int'),
    ('dias_arl', 'int'),
    ('dias_ccf', 'int'),

    # Salario (campos 40-41)
    ('salario_basico', 'amount'),
    ('tipo_salario', 'text'),

    # IBCs (campos 42-45)
    ('ibc_afp', 'amount'),
    ('ibc_eps', 'amount'),
    ('ibc_arl', 'amount'),
    ('ibc_ccf', 'amount'),

    # Pensión (campos 46-53)
    ('tarifa_afp', 'rate'),
    ('cotizacion_afp', 'amount'),
    ('avp_afiliado', 'amount'),
    ('avp_aportante', 'amount'),
    ('total_afp', 'amount'),
    ('aporte_fsp', 'amount'),
    ('aporte_fsps', 'amount'),
    ('valor_no_retenido', 'amount'),

    # Salud (campos 54-60)
    ('tarifa_eps', 'rate'),
    ('cotizacion_eps', 'amount'),
    ('valor_upc', 'amount'),
    ('numero_ige', 'text'),
    ('valor_ige', 'amount'),
    ('numero_lma', 'text'),
    ('valor_lma', 'amount'),

    # ARL (campos 61-63)
    ('tarifa_arl', 'rate'),
    ('centro_trabajo', 'text'),
    ('cotizacion_arl', 'amount'),

    # Parafiscales (campos 64-73)
    ('tarifa_ccf', 'rate'),
    ('aporte_ccf', 'amount'),
    ('tarifa_sena', 'rate'),
    ('aporte_sena', 'amount'),
    ('tarifa_icbf', 'rate'),
    ('aporte_icbf', 'amount'),
    ('tarifa_esap', 'rate'),
    ('aporte_esap', 'amount'),
    ('tarifa_men', 'rate'),
    ('aporte_men', 'amount'),

    # UPC + Exonerado (campos 74-76)
    ('tipo_documento_upc', 'text'),
    ('documento_upc', 'text'),
    ('exonerado', 'text'),

    # ARL detalle (campos 77-79)
    ('arl', 'text'),
    ('clase_riesgo', 'text'),
    ('tarifa_especial_afp', 'text'),

    # Fechas de novedades (campos 80-94)
    ('fecha_ing', 'date'),
    ('fecha_ret', 'date'),
    ('fecha_inicio_vsp', 'date'),
    ('fecha_inicio_sln', 'date'),
    ('fecha_fin_sln', 'date'),
    ('fecha_inicio_ige', 'date'),
    ('fecha_fin_ige', 'date'),
    ('fecha_inicio_lma', 'date'),
    ('fecha_fin_lma', 'date'),
    ('fecha_inicio_vac_lr', 'date'),
    ('fecha_fin_vac_lr', 'date'),
    ('fecha_inicio_vct', 'date'),
    ('fecha_fin_vct', 'date'),
    ('fecha_inicio_irl', 'date'),
    ('fecha_fin_irl', 'date'),

    # Campos finales (campos 95-98)
    ('ibc_otros_parafiscales', 'amount'),
    ('numero_horas_laboradas', 'int'),
    ('fecha_radicacion_exterior', 'date'),
    ('actividad_economica_arl', 'text'),
]


def generate_tipo_2(data: dict) -> str:
    """Genera un registro Tipo 2 (detalle de cotizante).

    Un registro Tipo 2 corresponde a un empleado/cotizante individual
    y contiene sus datos de identificación, novedades, días cotizados,
    bases de cotización (IBC), tarifas y aportes a cada subsistema
    (pensión, salud, riesgos laborales, parafiscales).

    Args:
        data: Diccionario con las claves que corresponden a los 98 campos
              del registro Tipo 2 de PILA. Las claves principales son:

              **Identificación (campos 1-14)**:
              tipo_registro ('2'), secuencia, tipo_documento,
              numero_documento, tipo_cotizante, subtipo_cotizante,
              extranjero, colombiano_exterior, departamento, municipio,
              primer_apellido, segundo_apellido, primer_nombre,
              segundo_nombre.

              **Novedades (campos 15-30)**:
              ing, ret, tde, tae, tdp, tap, vsp, linea, vst, sln, ige,
              lma, vac_lr, avp, vct, irl — cada una 'X' o vacío.

              **Administradoras (campos 31-35)**:
              afp, afp_traslado, eps, eps_traslado, ccf.

              **Días cotizados (campos 36-39)**:
              dias_afp, dias_eps, dias_arl, dias_ccf (int).

              **Salario (campos 40-41)**:
              salario_basico (float), tipo_salario ('X' o vacío).

              **IBCs (campos 42-45)**:
              ibc_afp, ibc_eps, ibc_arl, ibc_ccf (float).

              **Pensión (campos 46-53)**:
              tarifa_afp, cotizacion_afp, avp_afiliado, avp_aportante,
              total_afp, aporte_fsp, aporte_fsps, valor_no_retenido.

              **Salud (campos 54-60)**:
              tarifa_eps, cotizacion_eps, valor_upc, numero_ige,
              valor_ige, numero_lma, valor_lma.

              **ARL (campos 61-63)**:
              tarifa_arl, centro_trabajo, cotizacion_arl.

              **Parafiscales (campos 64-76)**:
              tarifa_ccf, aporte_ccf, tarifa_sena, aporte_sena,
              tarifa_icbf, aporte_icbf, tarifa_esap, aporte_esap,
              tarifa_men, aporte_men, tipo_documento_upc,
              documento_upc, exonerado.

              **ARL detalle (campos 77-79)**:
              arl, clase_riesgo, tarifa_especial_afp.

              **Fechas de novedades (campos 80-94)**:
              fecha_ing, fecha_ret, fecha_inicio_vsp,
              fecha_inicio_sln, fecha_fin_sln, fecha_inicio_ige,
              fecha_fin_ige, fecha_inicio_lma, fecha_fin_lma,
              fecha_inicio_vac_lr, fecha_fin_vac_lr,
              fecha_inicio_vct, fecha_fin_vct, fecha_inicio_irl,
              fecha_fin_irl.

              **Campos finales (campos 95-98)**:
              ibc_otros_parafiscales, numero_horas_laboradas,
              fecha_radicacion_exterior, actividad_economica_arl.

    Returns:
        Línea de texto con 98 campos separados por pipe ``|``.

    Examples:
        >>> data = {'tipo_registro': '2', 'secuencia': '00001',
        ...         'tipo_documento': 'CC', 'numero_documento': '123456789',
        ...         'tipo_cotizante': '01', 'subtipo_cotizante': '00',
        ...         'primer_apellido': 'García', 'primer_nombre': 'Juan',
        ...         'dias_afp': 30, 'salario_basico': 1300000.00,
        ...         'ibc_afp': 1300000.00, 'tarifa_afp': 0.16}
        >>> line = generate_tipo_2(data)
        >>> line.startswith('2|')
        True
    """
    fields: list[str] = []

    for field_name, field_type in _TIPO_2_FIELD_ORDER:
        value = data.get(field_name)

        if field_type == 'text':
            fields.append(_safe_str(value) if value is not None else '')
        elif field_type == 'name':
            fields.append(_fmt_text(value))
        elif field_type == 'amount':
            fields.append(
                _fmt_amount(value, decimals=2) if value is not None else ''
            )
        elif field_type == 'rate':
            # Tarifas con 5 decimales (ej: 0.16000 para 16%)
            fields.append(
                _fmt_amount(value, decimals=5) if value is not None else ''
            )
        elif field_type == 'int':
            fields.append(
                _fmt_amount(value, decimals=0) if value is not None else ''
            )
        elif field_type == 'date':
            fields.append(_fmt_date(value))
        else:
            fields.append(_safe_str(value))

    return '|'.join(fields)


# =====================================================================
# Registros de Totales — Tipos 8 a 12
# =====================================================================

def generate_tipo_8(data: dict) -> str:
    """Genera un registro Tipo 8 (totales por administradora de pensiones).

    Agrupa los aportes totales a una AFP específica.

    Args:
        data: Diccionario con las siguientes claves:
            - tipo_registro: str = '8'
            - secuencia: str
            - administradora: str (código AFP)
            - total_cotizantes: int
            - total_ibc: float
            - total_cotizacion: float
            - total_avp_afiliado: float
            - total_avp_aportante: float
            - total_aportes: float
            - total_fsp: float
            - total_fsps: float

    Returns:
        Línea de texto con campos separados por pipe ``|``.
    """
    fields = [
        _safe_str(data.get('tipo_registro', '8')),
        _safe_str(data.get('secuencia', '')),
        _safe_str(data.get('administradora', '')),
        _fmt_amount(data.get('total_cotizantes'), decimals=0),
        _fmt_amount(data.get('total_ibc'), decimals=2),
        _fmt_amount(data.get('total_cotizacion'), decimals=2),
        _fmt_amount(data.get('total_avp_afiliado'), decimals=2),
        _fmt_amount(data.get('total_avp_aportante'), decimals=2),
        _fmt_amount(data.get('total_aportes'), decimals=2),
        _fmt_amount(data.get('total_fsp'), decimals=2),
        _fmt_amount(data.get('total_fsps'), decimals=2),
    ]
    return '|'.join(fields)


def generate_tipo_9(data: dict) -> str:
    """Genera un registro Tipo 9 (totales por administradora de salud).

    Agrupa los aportes totales a una EPS específica.

    Args:
        data: Diccionario con las siguientes claves:
            - tipo_registro: str = '9'
            - secuencia: str
            - administradora: str (código EPS)
            - total_cotizantes: int
            - total_ibc: float
            - total_cotizacion: float
            - total_upc: float

    Returns:
        Línea de texto con campos separados por pipe ``|``.
    """
    fields = [
        _safe_str(data.get('tipo_registro', '9')),
        _safe_str(data.get('secuencia', '')),
        _safe_str(data.get('administradora', '')),
        _fmt_amount(data.get('total_cotizantes'), decimals=0),
        _fmt_amount(data.get('total_ibc'), decimals=2),
        _fmt_amount(data.get('total_cotizacion'), decimals=2),
        _fmt_amount(data.get('total_upc'), decimals=2),
    ]
    return '|'.join(fields)


def generate_tipo_10(data: dict) -> str:
    """Genera un registro Tipo 10 (totales por administradora de riesgos).

    Agrupa los aportes totales a una ARL específica.

    Args:
        data: Diccionario con las siguientes claves:
            - tipo_registro: str = '10'
            - secuencia: str
            - administradora: str (código ARL)
            - total_cotizantes: int
            - total_ibc: float
            - total_cotizacion: float

    Returns:
        Línea de texto con campos separados por pipe ``|``.
    """
    fields = [
        _safe_str(data.get('tipo_registro', '10')),
        _safe_str(data.get('secuencia', '')),
        _safe_str(data.get('administradora', '')),
        _fmt_amount(data.get('total_cotizantes'), decimals=0),
        _fmt_amount(data.get('total_ibc'), decimals=2),
        _fmt_amount(data.get('total_cotizacion'), decimals=2),
    ]
    return '|'.join(fields)


def generate_tipo_11(data: dict) -> str:
    """Genera un registro Tipo 11 (totales por caja de compensación).

    Agrupa los aportes totales a una CCF específica.

    Args:
        data: Diccionario con las siguientes claves:
            - tipo_registro: str = '11'
            - secuencia: str
            - administradora: str (código CCF)
            - total_cotizantes: int
            - total_ibc: float
            - total_aporte_ccf: float
            - total_aporte_sena: float
            - total_aporte_icbf: float
            - total_aporte_esap: float
            - total_aporte_men: float

    Returns:
        Línea de texto con campos separados por pipe ``|``.
    """
    fields = [
        _safe_str(data.get('tipo_registro', '11')),
        _safe_str(data.get('secuencia', '')),
        _safe_str(data.get('administradora', '')),
        _fmt_amount(data.get('total_cotizantes'), decimals=0),
        _fmt_amount(data.get('total_ibc'), decimals=2),
        _fmt_amount(data.get('total_aporte_ccf'), decimals=2),
        _fmt_amount(data.get('total_aporte_sena'), decimals=2),
        _fmt_amount(data.get('total_aporte_icbf'), decimals=2),
        _fmt_amount(data.get('total_aporte_esap'), decimals=2),
        _fmt_amount(data.get('total_aporte_men'), decimals=2),
    ]
    return '|'.join(fields)


def generate_tipo_12(data: dict) -> str:
    """Genera un registro Tipo 12 (totales generales de la planilla).

    Contiene los totales consolidados de toda la planilla.

    Args:
        data: Diccionario con las siguientes claves:
            - tipo_registro: str = '12'
            - secuencia: str
            - total_cotizantes: int
            - total_ibc_afp: float
            - total_ibc_eps: float
            - total_ibc_arl: float
            - total_ibc_ccf: float
            - total_cotizacion_afp: float
            - total_cotizacion_eps: float
            - total_cotizacion_arl: float
            - total_aporte_ccf: float
            - total_aporte_sena: float
            - total_aporte_icbf: float
            - total_aporte_esap: float
            - total_aporte_men: float
            - total_general: float

    Returns:
        Línea de texto con campos separados por pipe ``|``.
    """
    fields = [
        _safe_str(data.get('tipo_registro', '12')),
        _safe_str(data.get('secuencia', '')),
        _fmt_amount(data.get('total_cotizantes'), decimals=0),
        _fmt_amount(data.get('total_ibc_afp'), decimals=2),
        _fmt_amount(data.get('total_ibc_eps'), decimals=2),
        _fmt_amount(data.get('total_ibc_arl'), decimals=2),
        _fmt_amount(data.get('total_ibc_ccf'), decimals=2),
        _fmt_amount(data.get('total_cotizacion_afp'), decimals=2),
        _fmt_amount(data.get('total_cotizacion_eps'), decimals=2),
        _fmt_amount(data.get('total_cotizacion_arl'), decimals=2),
        _fmt_amount(data.get('total_aporte_ccf'), decimals=2),
        _fmt_amount(data.get('total_aporte_sena'), decimals=2),
        _fmt_amount(data.get('total_aporte_icbf'), decimals=2),
        _fmt_amount(data.get('total_aporte_esap'), decimals=2),
        _fmt_amount(data.get('total_aporte_men'), decimals=2),
        _fmt_amount(data.get('total_general'), decimals=2),
    ]
    return '|'.join(fields)


# =====================================================================
# Generación de resúmenes a partir de cotizantes
# =====================================================================

def _build_summary_records(cotizantes: list[dict]) -> list[str]:
    """Construye los registros de resumen (Tipo 8-12) desde los cotizantes.

    Agrupa los cotizantes por administradora para cada subsistema
    y genera los registros de totales correspondientes.

    Args:
        cotizantes: Lista de diccionarios (datos Tipo 2) de cotizantes.

    Returns:
        Lista de líneas de texto para los registros de resumen.
    """
    # Acumuladores por administradora
    afp_totals: dict[str, dict] = defaultdict(lambda: {
        'total_cotizantes': 0,
        'total_ibc': 0.0,
        'total_cotizacion': 0.0,
        'total_avp_afiliado': 0.0,
        'total_avp_aportante': 0.0,
        'total_aportes': 0.0,
        'total_fsp': 0.0,
        'total_fsps': 0.0,
    })

    eps_totals: dict[str, dict] = defaultdict(lambda: {
        'total_cotizantes': 0,
        'total_ibc': 0.0,
        'total_cotizacion': 0.0,
        'total_upc': 0.0,
    })

    arl_totals: dict[str, dict] = defaultdict(lambda: {
        'total_cotizantes': 0,
        'total_ibc': 0.0,
        'total_cotizacion': 0.0,
    })

    ccf_totals: dict[str, dict] = defaultdict(lambda: {
        'total_cotizantes': 0,
        'total_ibc': 0.0,
        'total_aporte_ccf': 0.0,
        'total_aporte_sena': 0.0,
        'total_aporte_icbf': 0.0,
        'total_aporte_esap': 0.0,
        'total_aporte_men': 0.0,
    })

    # Totales generales para Tipo 12
    gen = {
        'total_cotizantes': 0,
        'total_ibc_afp': 0.0,
        'total_ibc_eps': 0.0,
        'total_ibc_arl': 0.0,
        'total_ibc_ccf': 0.0,
        'total_cotizacion_afp': 0.0,
        'total_cotizacion_eps': 0.0,
        'total_cotizacion_arl': 0.0,
        'total_aporte_ccf': 0.0,
        'total_aporte_sena': 0.0,
        'total_aporte_icbf': 0.0,
        'total_aporte_esap': 0.0,
        'total_aporte_men': 0.0,
        'total_general': 0.0,
    }

    for cot in cotizantes:
        gen['total_cotizantes'] += 1

        # AFP (Tipo 8)
        afp_code = cot.get('afp', '')
        if afp_code:
            acc = afp_totals[afp_code]
            acc['total_cotizantes'] += 1
            acc['total_ibc'] += float(cot.get('ibc_afp') or 0)
            acc['total_cotizacion'] += float(cot.get('cotizacion_afp') or 0)
            acc['total_avp_afiliado'] += float(cot.get('avp_afiliado') or 0)
            acc['total_avp_aportante'] += float(
                cot.get('avp_aportante') or 0,
            )
            acc['total_aportes'] += float(cot.get('total_afp') or 0)
            acc['total_fsp'] += float(cot.get('aporte_fsp') or 0)
            acc['total_fsps'] += float(cot.get('aporte_fsps') or 0)

            gen['total_ibc_afp'] += float(cot.get('ibc_afp') or 0)
            gen['total_cotizacion_afp'] += float(
                cot.get('cotizacion_afp') or 0,
            )

        # EPS (Tipo 9)
        eps_code = cot.get('eps', '')
        if eps_code:
            acc = eps_totals[eps_code]
            acc['total_cotizantes'] += 1
            acc['total_ibc'] += float(cot.get('ibc_eps') or 0)
            acc['total_cotizacion'] += float(cot.get('cotizacion_eps') or 0)
            acc['total_upc'] += float(cot.get('valor_upc') or 0)

            gen['total_ibc_eps'] += float(cot.get('ibc_eps') or 0)
            gen['total_cotizacion_eps'] += float(
                cot.get('cotizacion_eps') or 0,
            )

        # ARL (Tipo 10)
        arl_code = cot.get('arl', '')
        if arl_code:
            acc = arl_totals[arl_code]
            acc['total_cotizantes'] += 1
            acc['total_ibc'] += float(cot.get('ibc_arl') or 0)
            acc['total_cotizacion'] += float(cot.get('cotizacion_arl') or 0)

            gen['total_ibc_arl'] += float(cot.get('ibc_arl') or 0)
            gen['total_cotizacion_arl'] += float(
                cot.get('cotizacion_arl') or 0,
            )

        # CCF (Tipo 11)
        ccf_code = cot.get('ccf', '')
        if ccf_code:
            acc = ccf_totals[ccf_code]
            acc['total_cotizantes'] += 1
            acc['total_ibc'] += float(cot.get('ibc_ccf') or 0)
            acc['total_aporte_ccf'] += float(cot.get('aporte_ccf') or 0)
            acc['total_aporte_sena'] += float(cot.get('aporte_sena') or 0)
            acc['total_aporte_icbf'] += float(cot.get('aporte_icbf') or 0)
            acc['total_aporte_esap'] += float(cot.get('aporte_esap') or 0)
            acc['total_aporte_men'] += float(cot.get('aporte_men') or 0)

            gen['total_ibc_ccf'] += float(cot.get('ibc_ccf') or 0)
            gen['total_aporte_ccf'] += float(cot.get('aporte_ccf') or 0)
            gen['total_aporte_sena'] += float(cot.get('aporte_sena') or 0)
            gen['total_aporte_icbf'] += float(cot.get('aporte_icbf') or 0)
            gen['total_aporte_esap'] += float(cot.get('aporte_esap') or 0)
            gen['total_aporte_men'] += float(cot.get('aporte_men') or 0)

    # Calcular total general
    gen['total_general'] = (
        gen['total_cotizacion_afp']
        + gen['total_cotizacion_eps']
        + gen['total_cotizacion_arl']
        + gen['total_aporte_ccf']
        + gen['total_aporte_sena']
        + gen['total_aporte_icbf']
        + gen['total_aporte_esap']
        + gen['total_aporte_men']
    )

    lines: list[str] = []
    seq = 1

    # Tipo 8 — AFP
    for code in sorted(afp_totals):
        acc = afp_totals[code]
        lines.append(generate_tipo_8({
            'tipo_registro': '8',
            'secuencia': str(seq).zfill(5),
            'administradora': code,
            **acc,
        }))
        seq += 1

    # Tipo 9 — EPS
    for code in sorted(eps_totals):
        acc = eps_totals[code]
        lines.append(generate_tipo_9({
            'tipo_registro': '9',
            'secuencia': str(seq).zfill(5),
            'administradora': code,
            **acc,
        }))
        seq += 1

    # Tipo 10 — ARL
    for code in sorted(arl_totals):
        acc = arl_totals[code]
        lines.append(generate_tipo_10({
            'tipo_registro': '10',
            'secuencia': str(seq).zfill(5),
            'administradora': code,
            **acc,
        }))
        seq += 1

    # Tipo 11 — CCF
    for code in sorted(ccf_totals):
        acc = ccf_totals[code]
        lines.append(generate_tipo_11({
            'tipo_registro': '11',
            'secuencia': str(seq).zfill(5),
            'administradora': code,
            **acc,
        }))
        seq += 1

    # Tipo 12 — Totales generales
    lines.append(generate_tipo_12({
        'tipo_registro': '12',
        'secuencia': str(seq).zfill(5),
        **gen,
    }))

    return lines


# =====================================================================
# Función principal — Generación del archivo PILA completo
# =====================================================================

def generate_pila_file(aportante: dict, cotizantes: list[dict]) -> str:
    """Genera el contenido completo del archivo plano PILA.

    Orquesta la generación de todos los tipos de registro:
        1. Registro Tipo 1 (encabezado) a partir de los datos del aportante.
        2. Registros Tipo 2 (detalle) por cada cotizante.
        3. Registros Tipo 8-12 (resúmenes) calculados automáticamente.

    Args:
        aportante: Diccionario con los datos del aportante para el
                   registro Tipo 1. Ver :func:`generate_tipo_1` para
                   el detalle de claves esperadas.
        cotizantes: Lista de diccionarios, uno por cotizante, con los
                    datos para registros Tipo 2. Ver :func:`generate_tipo_2`
                    para el detalle de claves esperadas.

    Returns:
        Contenido completo del archivo PILA como string UTF-8.
        Cada registro ocupa una línea, separada por ``\\n``.

    Examples:
        >>> aportante = {
        ...     'tipo_registro': '1', 'modalidad': '1', 'secuencia': '1',
        ...     'razon_social': 'InSoTech SAS', 'tipo_documento': 'NI',
        ...     'numero_documento': '901797249',
        ...     'digito_verificacion': '5', 'tipo_planilla': 'E',
        ...     'forma_presentacion': 'U', 'codigo_arl': '14-23',
        ...     'periodo_pago_otros': '2024-01',
        ...     'periodo_pago_salud': '2024-01',
        ...     'numero_planilla': '0001', 'total_cotizantes': 1,
        ...     'valor_total_nomina': 1300000.00,
        ...     'tipo_aportante': '1', 'codigo_operador': '01',
        ... }
        >>> cotizantes = [{
        ...     'tipo_registro': '2', 'secuencia': '00001',
        ...     'tipo_documento': 'CC', 'numero_documento': '123456789',
        ...     'tipo_cotizante': '01', 'subtipo_cotizante': '00',
        ...     'primer_apellido': 'García', 'primer_nombre': 'Juan',
        ...     'afp': 'AFP001', 'eps': 'EPS001', 'arl': 'ARL001',
        ...     'ccf': 'CCF001', 'dias_afp': 30, 'dias_eps': 30,
        ...     'dias_arl': 30, 'dias_ccf': 30,
        ...     'salario_basico': 1300000.00, 'ibc_afp': 1300000.00,
        ...     'ibc_eps': 1300000.00, 'ibc_arl': 1300000.00,
        ...     'ibc_ccf': 1300000.00,
        ... }]
        >>> content = generate_pila_file(aportante, cotizantes)
        >>> content.startswith('1|')
        True
        >>> len(content.strip().split('\\n')) >= 3
        True
    """
    lines: list[str] = []

    # Tipo 1 — Encabezado
    lines.append(generate_tipo_1(aportante))

    # Tipo 2 — Detalle de cotizantes
    for cotizante in cotizantes:
        lines.append(generate_tipo_2(cotizante))

    # Tipos 8-12 — Resúmenes
    summary_lines = _build_summary_records(cotizantes)
    lines.extend(summary_lines)

    return '\n'.join(lines) + '\n'
