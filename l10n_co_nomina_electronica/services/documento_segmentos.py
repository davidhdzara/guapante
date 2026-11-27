# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Segmentos del mes de un empleado (H-F3-04, opcion A del doc 95; decisiones del TL del 23-nov, doc 98).

Funcion PURA (sin Odoo ni base de datos): recibe las claves de los recibos del empleado en el mes, YA ORDENADAS
en el tiempo, y las parte en RACHAS CONSECUTIVAS de la misma clave. Cada racha es un segmento y de cada segmento
sale un documento mensual propio; del segundo en adelante el XML lleva ``Novedad = true`` con el CUNE del inmediato
anterior (Anexo Tecnico NIE199 y NIE204).

Reglas:
- La clave es lo que el llamador decide (hoy el tipo y el subtipo de trabajador; el porcentaje NO entra: un
  porcentaje distinto con el mismo tipo sigue deteniendo la fusion con ``ErrorFusion``).
- CONSECUTIVOS: A, B, A da TRES segmentos (la cadena de ``CUNENov`` sigue el orden en el tiempo y no se reordena
  un documento ya transmitido).
- Una clave ``None`` (el llamador no pudo resolverla: dato incompleto, que ya avisa la validacion del recibo) no
  abre ni cierra un segmento: se suma al segmento abierto, o al primero si es el primer recibo.

NO VERIFICADO con la DIAN (doc 95 §4): que un cambio de tipo de trabajador sea una novedad contractual y que
acepte los documentos asi partidos.
"""


def segmentar(claves):
    """Devuelve una lista de segmentos; cada segmento es la lista de POSICIONES (0, 1, 2...) de ``claves``.

    ``claves`` es una lista ordenada de claves comparables (o ``None``). Lista vacia -> lista vacia."""
    segmentos = []
    clave_abierta = None
    for posicion, clave in enumerate(claves):
        if clave is None:
            if segmentos:
                segmentos[-1].append(posicion)
            else:
                segmentos.append([posicion])
            continue
        if not segmentos or (clave_abierta is not None and clave != clave_abierta):
            segmentos.append([posicion])
        else:
            segmentos[-1].append(posicion)
        clave_abierta = clave
    return segmentos
