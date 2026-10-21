"""Cálculo de CUNE — Código Único de Nómina Electrónica.

Implementa el algoritmo de generación del CUNE según el Anexo Técnico
de Nómina Electrónica de la DIAN (Resolución 000013 de 2021).

El CUNE se calcula como SHA-384 de la concatenación de:
    NumNE + FecNE + HorNE + ValDev + ValDed + ValTolNE +
    NitNE + DocTrab + ClNE + SoftwarePin + TipoAmb

Todas las funciones son puras — sin efectos secundarios ni
dependencias de Odoo.
"""

import hashlib
import math
from typing import Union


def _truncate_amount(value: Union[str, float]) -> str:
    """Formatea un monto truncando (no redondeando) a 2 decimales.

    El Anexo Técnico exige decimales *truncados* a dos dígitos.
    """
    return '%.2f' % (math.trunc(float(value) * 100) / 100)


def compute_cune(
    num_ne: str,
    fec_ne: str,
    hor_ne: str,
    val_dev: Union[str, float],
    val_ded: Union[str, float],
    val_tol: Union[str, float],
    nit_ne: str,
    doc_trab: str,
    cl_ne: str,
    tipo_amb: str,
    software_pin: str = '',
) -> tuple[str, str]:
    """Calcula el CUNE (Código Único de Nómina Electrónica).

    Concatena los campos en orden y aplica SHA-384.

    Args:
        num_ne: Número del documento de nómina electrónica
                (ej: 'NE001').
        fec_ne: Fecha de generación formato YYYY-MM-DD
                (ej: '2024-01-15').
        hor_ne: Hora de generación formato HH:MM:SS-05:00
                (ej: '10:30:00-05:00').
        val_dev: Total devengados con 2 decimales
                 (ej: '2500000.00' o 2500000.00).
        val_ded: Total deducciones con 2 decimales
                 (ej: '350000.00' o 350000.00).
        val_tol: Total comprobante con 2 decimales
                 (ej: '2150000.00' o 2150000.00).
        nit_ne: NIT del empleador sin DV (ej: '901797249').
        doc_trab: Número de documento del trabajador
                  (ej: '1234567890').
        cl_ne: Código del tipo de XML:
               '102' para nómina individual,
               '103' para nómina de ajuste.
        software_pin: PIN del software asignado por la DIAN.
        tipo_amb: Tipo de ambiente:
                  '1' para producción,
                  '2' para habilitación/pruebas.

    Returns:
        Tupla (cune_hex, raw_string) donde:
        - cune_hex: Hash SHA-384 en hexadecimal (96 caracteres).
        - raw_string: Cadena concatenada antes del hash (para debug).

    Examples:
        >>> cune, raw = compute_cune(
        ...     'NE001', '2024-01-15', '10:30:00-05:00',
        ...     '2500000.00', '350000.00', '2150000.00',
        ...     '901797249', '1234567890', '102', '2', '693'
        ... )
        >>> len(cune)
        96
    """
    # Montos con 2 decimales truncados (Anexo Técnico DIAN)
    val_dev_str = _truncate_amount(val_dev)
    val_ded_str = _truncate_amount(val_ded)
    val_tol_str = _truncate_amount(val_tol)

    raw = (
        str(num_ne)
        + str(fec_ne)
        + str(hor_ne)
        + val_dev_str
        + val_ded_str
        + val_tol_str
        + str(nit_ne)
        + str(doc_trab)
        + str(cl_ne)
        + str(software_pin)
        + str(tipo_amb)
    )

    cune_hex = hashlib.sha384(raw.encode('utf-8')).hexdigest()
    return cune_hex, raw


def compute_software_security_code(
    software_id: str,
    pin: str,
    doc_number: str,
) -> str:
    """Calcula el código de seguridad del software (SoftwareSC).

    El SoftwareSC se usa en el elemento ProveedorXML del XML de nómina
    y se calcula como SHA-384(SoftwareID + PIN + NumeroDocumento).

    Args:
        software_id: Identificador del software asignado por la DIAN
                     (ej: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx').
        pin: PIN del software asignado por la DIAN
             (ej: '12345').
        doc_number: Número del documento de nómina electrónica
                    (ej: 'NE001').

    Returns:
        Hash SHA-384 en hexadecimal (96 caracteres).

    Examples:
        >>> sc = compute_software_security_code(
        ...     'abc-def-123', '12345', 'NE001'
        ... )
        >>> len(sc)
        96
    """
    raw = str(software_id) + str(pin) + str(doc_number)
    return hashlib.sha384(raw.encode('utf-8')).hexdigest()
