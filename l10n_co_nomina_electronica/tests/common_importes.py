# -*- coding: utf-8 -*-
"""Utilidad de pruebas: los importes de los informes salen con el widget monetario nativo, que usa el formato del idioma
del usuario o de la compañía (en_US ``3,000,000.00``; es_CO ``3.000.000,00``). Las pruebas NO deben depender del idioma:
se extraen los números de los ``oe_currency_value`` y se comparan como valores."""
import re

_VALOR = re.compile(r'<span class="oe_currency_value">([^<]+)</span>')


def a_numero(texto):
    """'3.000.000,00' o '3,000,000.00' (o sin decimales) -> 3000000.0. Si el último separador va seguido de exactamente
    dos dígitos es el decimal; si no, todos los separadores son de miles."""
    texto = texto.strip().replace('\xa0', '').replace(' ', '')
    negativo = texto.startswith('-')
    texto = texto.lstrip('-')
    decimal = re.search(r'[.,](\d{2})$', texto)
    if decimal:
        entero = re.sub(r'[.,]', '', texto[:decimal.start()])
        valor = float('%s.%s' % (entero, decimal.group(1)))
    else:
        valor = float(re.sub(r'[.,]', '', texto))
    return -valor if negativo else valor


def valores_monetarios(html):
    """Lista de los importes (float) que el informe imprimió con el widget monetario."""
    return [a_numero(t) for t in _VALOR.findall(html)]
