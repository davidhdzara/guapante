"""Montos de la nómina electrónica DIAN: el único truncado para el XML y el CUNE.

Módulo puro de Python, sin dependencias: lo importan ``dian_utils``, ``cune`` y
``nomina_xml_builder`` (los dos primeros se importan entre sí, por eso va aparte).
"""

from decimal import ROUND_DOWN, Decimal
from typing import Union


def format_amount(value: Union[int, float, str, Decimal], decimals: int = 2) -> str:
    """Formatea un valor numérico a string con N decimales truncados.

    El Anexo Técnico DIAN pide los montos con 2 decimales *truncados* (no
    redondeados). Q-10 (.332): truncar sobre el punto flotante quitaba un
    centavo (166063.33 salía '166063.32'), así que primero se quita el error
    binario (se redondea con 4 decimales más de los pedidos) y se trunca en
    ``Decimal``.

    Args:
        value: Valor numérico (int, float, Decimal o string numérico).
        decimals: Cantidad de decimales.

    Returns:
        String con los decimales truncados hacia cero (ej: '1500000.00').

    Examples:
        >>> format_amount(1500000)
        '1500000.00'
        >>> format_amount('25000.5')
        '25000.50'
        >>> format_amount('25000.999')
        '25000.99'
        >>> format_amount(166063.33)
        '166063.33'
    """
    exacto = Decimal(str(round(float(value), decimals + 4)))
    truncado = exacto.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_DOWN)
    return str(truncado if truncado else truncado.copy_abs())    # sin «-0.00»
