# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""Interpretación de las respuestas de la DIAN (parte A: helpers; parte B: veredicto neutral).

Python puro, SIN dependencias de Odoo (convención de ``services/``). Estos 4 helpers vivían en
``models/l10n_co_ne_documento_mixin.py`` y no leen ningún campo del recibo; se extraen aquí para que
el recibo (mixin) y el documento mensual interpreten la respuesta con UNA sola implementación (doc 53
§23.12, decisión de Tech Lead: dos copias del parseo de respuestas ya causaron el incidente DIAN del
2026-09-14).

El mixin conserva sus 4 nombres (``_ne_response_text``, ``_ne_cune_candidates``,
``_ne_number_candidates``, ``_ne_is_set_level_status``) como envoltorios delgados que llaman aquí:
el comportamiento del recibo no cambia.
"""

from typing import NamedTuple, Optional

from . import soap_client

# Tope del resumen que se guarda en el formulario (la evidencia completa vive en l10n.co.ne.exchange).
LIMITE_TEXTO_RESPUESTA = 5000


def texto_respuesta(value, limite=LIMITE_TEXTO_RESPUESTA):
    """Resumen de texto de un sobre SOAP/ZIP de respuesta, recortado a ``limite`` caracteres.

    AUD-DIAN-34 (2026-10-04): este texto es un resumen para la vista, no evidencia -- la evidencia
    completa (sobre SOAP y ZIP de respuesta íntegros, sin truncar) vive en l10n.co.ne.exchange. Un
    SendTestSetAsync de 4 nóminas puede traer un ZIP base64 de varios MB; guardarlo entero en el
    registro lo infla sin necesidad.

    ``bytes`` se decodifica como utf-8 con ``errors='replace'``; ``None`` o vacío devuelve ''.
    """
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    return (value or '')[:limite]


def candidatos_cune(result):
    """Candidatos de CUNE de un resultado, sin confundirlos con IDs SOAP.

    AUD-DIAN-34 (2026-10-04): evidencia real (GetStatusZip AUTORIZADO, nómina SME-10) confirma que
    el CUNE del documento original viaja en
    ``cac:DocumentResponse/cac:DocumentReference/cbc:UUID`` dentro del ApplicationResponse -- ver
    ``soap_client.extract_document_cunes``.

    Args:
        result: dict de un resultado de la DIAN (claves ``XmlDocumentKey``, ``CUNE``,
            ``DocumentKey`` y ``ApplicationResponse``).

    Returns:
        ``set`` de str (cada valor de clave sin espacios en los extremos).
    """
    candidates = set()
    for key in ('XmlDocumentKey', 'CUNE', 'DocumentKey'):
        value = result.get(key)
        if value:
            candidates.add(value.strip())
    application = result.get('ApplicationResponse') or ''
    if application:
        candidates.update(soap_client.extract_document_cunes(application))
    return candidates


def candidatos_numero(result):
    """NÚMERO de negocio del documento original (no es CUNE).

    ``cac:DocumentResponse/cac:DocumentReference/cbc:ID`` -- solo se usa como respaldo cuando la
    DIAN no entrega CUNE (ver ``soap_client.extract_document_numbers``).

    Returns:
        ``set`` de str; vacío si el resultado no trae ``ApplicationResponse``.
    """
    application = result.get('ApplicationResponse') or ''
    if not application:
        return set()
    return soap_client.extract_document_numbers(application)


def es_respuesta_de_set(response):
    """True si la respuesta de GetStatusZip es sobre el SET de pruebas completo, no sobre el
    documento individual consultado.

    H-012 (2026-10-06): evidencia real (NA0000000049, payslip 944, ZipKey 98e2fdc3) -- GetStatusZip
    respondió StatusCode="2", IsValid="false", StatusDescription="Set de prueba con identificador
    e07c1748... se encuentra Aceptado.", sin XmlDocumentKey ni ApplicationResponse (ningún dato que
    identifique el documento). Esa combinación (StatusCode 2 + IsValid false + cero datos de
    documento) es la FORMA de una respuesta de nivel set, no una hipótesis sobre por qué la DIAN
    respondió así -- no se asume la causa (Tech Lead: "mi hipótesis no está confirmada, el fix no
    debe depender de ella").

    ``IsValid`` se compara en minúsculas ('true', 'True' y 'TRUE' son lo mismo).
    """
    if str(response.get('StatusCode', '')).strip() != '2':
        return False
    if str(response.get('IsValid', '')).lower() == 'true':
        return False
    return not response.get('XmlDocumentKey') and not response.get('ApplicationResponse')


# =====================================================================
# Parte B: veredicto NEUTRAL de una respuesta (doc 53 §23.13, decisión (d) de Tech Lead)
# =====================================================================
#
# Esta función dice QUÉ respondió la DIAN, sin asumir nada de ningún modelo: cada modelo traduce el
# veredicto a su propio vocabulario de estados (el recibo, a ``l10n_co_ne_state``; el documento
# mensual, al estado de su intento). Por eso NO conoce ``accepted``/``rejected``/``invoice_*``.
# TODAVÍA NO LA USA NADIE: el recibo sigue con su regla actual (commit 10, atado a la respuesta de
# David) y el documento la adopta al implementar enviar/reconsultar (commits 4 y 5 de §23.14).

ACEPTADO = 'aceptado'
RECHAZADO = 'rechazado'
PENDIENTE = 'pendiente'
ERROR_TRANSPORTE = 'error_transporte'
NIVEL_SET = 'nivel_set'

CONTEXTO_ENVIO = 'envio'
CONTEXTO_CONSULTA = 'consulta'

DIAGNOSTICO_IDENTIFICACION = 'identificacion'
DIAGNOSTICO_CORREO = 'correo'
DIAGNOSTICO_CUENTA = 'cuenta'
DIAGNOSTICO_SALARIO = 'salario'


class ResultadoDian(NamedTuple):
    """Veredicto neutral de una respuesta de la DIAN."""
    veredicto: str                      # ACEPTADO | RECHAZADO | PENDIENTE | ERROR_TRANSPORTE | NIVEL_SET
    mensaje: str                        # StatusDescription / StatusMessage, o el detalle de errores
    errores: tuple                      # ErrorMessages (o (ErrorMessage,)); () si no hay
    zip_key: str                        # ZipKey si viene, '' si no
    diagnostico: Optional[str]          # clave de diagnostico() solo si veredicto == RECHAZADO


def es_rechazo(response):
    """True si la respuesta trae evidencia de RECHAZO de la DIAN: ``StatusCode == '99'`` o la lista
    ``ErrorMessages`` con contenido.

    AUD-DIAN-34 (2026-10-04): el Anexo Técnico no trae una tabla exhaustiva de StatusCode de
    GetStatusZip, solo el ejemplo real de rechazo (IsValid=false, StatusCode=99, con ErrorMessage
    poblado de reglas NIE/ZB). No se supone ningún otro código como rechazo: un estado pendiente o
    incompleto NO es un rechazo.
    """
    return str(response.get('StatusCode', '')).strip() == '99' or bool(response.get('ErrorMessages'))


def _es_error_de_transporte(response):
    """True si la respuesta NO trae un veredicto interpretable de la DIAN (falló el transporte o la
    infraestructura): nunca debe tratarse como rechazo del documento.

    Casos (``soap_client._send`` los arma así):
    - ``TransportError`` o ``StatusCode == 'CONNECTION_ERROR'`` (``requests.RequestException``).
    - Falla SOAP (``SOAPFault`` / ``FaultDetails``).
    - ``HttpStatus`` >= 500.
    - Cualquier ``HttpStatus`` >= 400 SIN ``IsValid``: un HTTP 4xx no es un veredicto sobre el
      documento (decisión de Tech Lead). ``soap_client`` rellena ``StatusCode`` con el código HTTP
      cuando la DIAN no lo trae, así que ``StatusCode`` solo no basta para distinguirlo.
    - Ni ``IsValid`` ni ``StatusCode``: no hay veredicto.
    """
    if response.get('TransportError'):
        return True
    codigo = str(response.get('StatusCode', '')).strip()
    if codigo == 'CONNECTION_ERROR':
        return True
    if response.get('SOAPFault') or response.get('FaultDetails'):
        return True
    try:
        http = int(response.get('HttpStatus') or 0)
    except (TypeError, ValueError):
        http = 0
    if http >= 500:
        return True
    tiene_is_valid = 'IsValid' in response
    if http >= 400 and not tiene_is_valid:
        return True
    return not tiene_is_valid and not codigo


def _errores(response):
    lista = response.get('ErrorMessages')
    if lista:
        return tuple(str(e) for e in lista)
    unico = response.get('ErrorMessage')
    return (str(unico),) if unico else ()


def diagnosticar(detalle):
    """Clasificación por palabras clave del detalle de un rechazo: solo la CLAVE; los textos y los
    enlaces (que dependen del empleado o del contrato) los pone cada modelo.

    Misma regla y mismo orden que el diagnóstico del chatter del recibo: la primera coincidencia
    gana. Se conserva tal cual, incluida la palabra ``documento`` (cae en identificación para casi
    cualquier mensaje que la contenga) y ``identificacion`` sin tilde: defecto menor registrado en
    §23.13, no se corrige aquí.

    Returns:
        ``'identificacion'`` | ``'correo'`` | ``'cuenta'`` | ``'salario'`` | ``None``.
    """
    texto = (detalle or '').lower()
    if 'nit' in texto or 'documento' in texto or 'identificacion' in texto:
        return DIAGNOSTICO_IDENTIFICACION
    if 'correo' in texto or 'email' in texto:
        return DIAGNOSTICO_CORREO
    if 'cuenta' in texto or 'banco' in texto or 'metodo' in texto:
        return DIAGNOSTICO_CUENTA
    if 'salario' in texto or 'ibc' in texto or 'minimo' in texto:
        return DIAGNOSTICO_SALARIO
    return None


def interpretar_respuesta(response, *, contexto):
    """Veredicto neutral de una respuesta de la DIAN (``SendNominaSync`` o ``GetStatusZip``).

    Args:
        response: dict de ``soap_client`` (o un resultado individual de ``DianResponses``).
        contexto: ``'envio'`` o ``'consulta'`` (otro valor -> ``ValueError``). Solo ``'consulta'``
            reconoce la respuesta de nivel SET.

    Orden de evaluación (§23.13):
      1. ``error_transporte``: no hay veredicto DIAN interpretable (ver ``_es_error_de_transporte``).
      2. ``nivel_set``: solo ``consulta`` y ``es_respuesta_de_set``.
      3. ``aceptado``: ``IsValid`` en minúsculas es ``'true'`` ('true', 'True' y 'TRUE' son lo mismo;
         cambio intencional frente al ``== 'true'`` exacto del envío por recibo, en dirección segura).
      4. ``rechazado``: no válido y ``es_rechazo``.
      5. ``pendiente``: cualquier otro caso (p. ej. "Batch en proceso de validación").

    Nunca devuelve ``rechazado`` para algo que la DIAN no procesó.
    """
    if contexto not in (CONTEXTO_ENVIO, CONTEXTO_CONSULTA):
        raise ValueError('contexto debe ser %r o %r, no %r' % (
            CONTEXTO_ENVIO, CONTEXTO_CONSULTA, contexto))
    errores = _errores(response)
    mensaje = (response.get('StatusDescription') or response.get('StatusMessage')
               or '; '.join(errores))
    zip_key = str(response.get('ZipKey') or '')

    def resultado(veredicto, diagnostico=None):
        return ResultadoDian(veredicto, mensaje, errores, zip_key, diagnostico)

    if _es_error_de_transporte(response):
        return resultado(ERROR_TRANSPORTE)
    if contexto == CONTEXTO_CONSULTA and es_respuesta_de_set(response):
        return resultado(NIVEL_SET)
    if str(response.get('IsValid', '')).lower() == 'true':
        return resultado(ACEPTADO)
    if es_rechazo(response):
        return resultado(RECHAZADO, diagnosticar('; '.join(errores)))
    return resultado(PENDIENTE)
