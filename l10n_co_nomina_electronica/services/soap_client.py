"""Cliente SOAP para los web services de Nómina Electrónica DIAN.

Implementa las operaciones necesarias para nómina electrónica:
- SendNominaSync: enviar nómina individual de forma síncrona
- SendTestSetAsync: enviar set de pruebas
- GetStatusZip: consultar estado de un envío

Usa SOAP 1.2 + WS-Addressing + WS-Security con:
- TransportBinding (HTTPS)
- EndorsingSupportingTokens (X509 endosa Timestamp)
- ThumbprintReference para el key identifier
- Firma wsa:To + Timestamp
- AlgorithmSuite: Basic256Sha256Rsa15

Adaptado de insotech_dian_wizard/services/soap_client.py para nómina
electrónica, sin dependencias de Odoo ni de test_data.

Dependencias externas:
    - requests (pip install requests)
    - cryptography (pip install cryptography)
    - lxml (pip install lxml)
"""

import base64
import hashlib
import io
import logging
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography import x509
from lxml import etree

_logger = logging.getLogger(__name__)

# =====================================================================
# Constantes — definidas inline (sin dependencia de test_data)
# =====================================================================

SOAP_TIMEOUT = 45

# Endpoints DIAN
DIAN_ENDPOINT_HAB = (
    'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc'
)
DIAN_ENDPOINT_PROD = (
    'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc'
)

# SOAP Actions para nómina electrónica
SOAP_ACTION_SEND_NOMINA = (
    'http://wcf.dian.colombia/IWcfDianCustomerServices'
    '/SendNominaSync'
)
SOAP_ACTION_SEND_TEST_SET = (
    'http://wcf.dian.colombia/IWcfDianCustomerServices'
    '/SendTestSetAsync'
)
SOAP_ACTION_GET_STATUS = (
    'http://wcf.dian.colombia/IWcfDianCustomerServices'
    '/GetStatusZip'
)

# Namespace WCF DIAN
WCF_NS = 'http://wcf.dian.colombia'

# Namespaces SOAP / WS-*
SOAP_NS = 'http://www.w3.org/2003/05/soap-envelope'
WSA_NS = 'http://www.w3.org/2005/08/addressing'
WSSE_NS = (
    'http://docs.oasis-open.org/wss/2004/01/'
    'oasis-200401-wss-wssecurity-secext-1.0.xsd'
)
WSU_NS = (
    'http://docs.oasis-open.org/wss/2004/01/'
    'oasis-200401-wss-wssecurity-utility-1.0.xsd'
)
DS_NS = 'http://www.w3.org/2000/09/xmldsig#'

# Perfiles de seguridad
TOKEN_PROFILE = (
    'http://docs.oasis-open.org/wss/2004/01/'
    'oasis-200401-wss-x509-token-profile-1.0#X509v3'
)
ENCODING_TYPE = (
    'http://docs.oasis-open.org/wss/2004/01/'
    'oasis-200401-wss-soap-message-security-1.0#Base64Binary'
)
THUMBPRINT_TYPE = (
    'http://docs.oasis-open.org/wss/oasis-wss-soap-message-security'
    '-1.1#ThumbprintSHA1'
)

# Algoritmos (Basic256Sha256Rsa15)
C14N_ALG = 'http://www.w3.org/2001/10/xml-exc-c14n#'
SHA256_ALG = 'http://www.w3.org/2001/04/xmlenc#sha256'
RSA_SHA256_ALG = (
    'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
)


# =====================================================================
# Funciones auxiliares de criptografía
# =====================================================================

def _c14n(elem) -> bytes:
    """Exclusive C14N de un elemento XML.

    Args:
        elem: Elemento lxml.

    Returns:
        Bytes del elemento canonicalizado.
    """
    return etree.tostring(elem, method='c14n', exclusive=True)


def _sha256_b64(data: bytes) -> str:
    """SHA-256 digest codificado en base64.

    Args:
        data: Datos binarios a digerir.

    Returns:
        Digest en base64.
    """
    return base64.b64encode(
        hashlib.sha256(data).digest()
    ).decode('ascii')


def _sha1_b64(data: bytes) -> str:
    """SHA-1 digest codificado en base64 (para thumbprint).

    Args:
        data: Datos binarios a digerir.

    Returns:
        Digest SHA-1 en base64.
    """
    return base64.b64encode(
        hashlib.sha1(data).digest()
    ).decode('ascii')


def _sign(private_key, data: bytes) -> str:
    """Firma RSA-SHA256 codificada en base64.

    Args:
        private_key: Clave privada RSA.
        data: Datos binarios a firmar.

    Returns:
        Firma en base64.
    """
    sig = private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode('ascii')


# =====================================================================
# Construcción del sobre SOAP con WS-Security
# =====================================================================

def _build_envelope(
    action: str,
    endpoint: str,
    body_xml: str,
    cert_der: bytes,
    private_key,
) -> bytes:
    """Construye SOAP 1.2 con WS-Security (TransportBinding +
    EndorsingSupportingTokens).

    La política de la DIAN requiere:
    - TransportBinding con HTTPS (sin firmar Body)
    - EndorsingSupportingTokens: X509 que endosa el Timestamp
    - SignedParts: wsa:To header
    - ThumbprintReference para key identifier

    Args:
        action: SOAP Action URL.
        endpoint: URL del web service DIAN.
        body_xml: Cuerpo XML como string.
        cert_der: Certificado en formato DER.
        private_key: Clave privada RSA.

    Returns:
        Sobre SOAP como bytes UTF-8.
    """
    now = datetime.now(timezone.utc)
    created = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    expires = (now + timedelta(minutes=5)).strftime(
        '%Y-%m-%dT%H:%M:%S.000Z'
    )

    # IDs
    ts_id = '_0'
    bst_id = 'uuid-%s-1' % uuid.uuid4()
    to_id = '_1'

    cert_der_b64 = base64.b64encode(cert_der).decode('ascii')
    cert_thumbprint = _sha1_b64(cert_der)

    # Construir árbol XML
    nsmap = {
        'soap': SOAP_NS,
        'wsa': WSA_NS,
        'wsse': WSSE_NS,
        'wsu': WSU_NS,
    }

    env = etree.Element('{%s}Envelope' % SOAP_NS, nsmap=nsmap)

    # --- Header ---
    header = etree.SubElement(env, '{%s}Header' % SOAP_NS)

    # wsa:Action
    act = etree.SubElement(header, '{%s}Action' % WSA_NS)
    act.set('{%s}mustUnderstand' % SOAP_NS, '1')
    act.text = action

    # wsa:To (con wsu:Id para firmar)
    to = etree.SubElement(header, '{%s}To' % WSA_NS)
    to.set('{%s}mustUnderstand' % SOAP_NS, '1')
    to.set('{%s}Id' % WSU_NS, to_id)
    to.text = endpoint

    # wsse:Security
    sec = etree.SubElement(header, '{%s}Security' % WSSE_NS)
    sec.set('{%s}mustUnderstand' % SOAP_NS, '1')

    # Timestamp
    ts = etree.SubElement(sec, '{%s}Timestamp' % WSU_NS)
    ts.set('{%s}Id' % WSU_NS, ts_id)
    etree.SubElement(ts, '{%s}Created' % WSU_NS).text = created
    etree.SubElement(ts, '{%s}Expires' % WSU_NS).text = expires

    # BinarySecurityToken
    bst = etree.SubElement(sec, '{%s}BinarySecurityToken' % WSSE_NS)
    bst.set('EncodingType', ENCODING_TYPE)
    bst.set('ValueType', TOKEN_PROFILE)
    bst.set('{%s}Id' % WSU_NS, bst_id)
    bst.text = cert_der_b64

    # --- Body ---
    body = etree.SubElement(env, '{%s}Body' % SOAP_NS)
    body_content = etree.fromstring(body_xml)
    body.append(body_content)

    # === Firma (Endorsing: firma Timestamp + wsa:To) ===

    # Digest del Timestamp
    ts_digest = _sha256_b64(_c14n(ts))

    # Digest del wsa:To
    to_digest = _sha256_b64(_c14n(to))

    # Signature element
    sig = etree.SubElement(sec, '{%s}Signature' % DS_NS)

    # SignedInfo
    si = etree.SubElement(sig, '{%s}SignedInfo' % DS_NS)
    etree.SubElement(
        si, '{%s}CanonicalizationMethod' % DS_NS,
        Algorithm=C14N_ALG,
    )
    etree.SubElement(
        si, '{%s}SignatureMethod' % DS_NS,
        Algorithm=RSA_SHA256_ALG,
    )

    # Reference: Timestamp
    ref1 = etree.SubElement(si, '{%s}Reference' % DS_NS,
                            URI='#%s' % ts_id)
    t1 = etree.SubElement(ref1, '{%s}Transforms' % DS_NS)
    etree.SubElement(t1, '{%s}Transform' % DS_NS,
                     Algorithm=C14N_ALG)
    etree.SubElement(ref1, '{%s}DigestMethod' % DS_NS,
                     Algorithm=SHA256_ALG)
    etree.SubElement(
        ref1, '{%s}DigestValue' % DS_NS,
    ).text = ts_digest

    # Reference: wsa:To
    ref2 = etree.SubElement(si, '{%s}Reference' % DS_NS,
                            URI='#%s' % to_id)
    t2 = etree.SubElement(ref2, '{%s}Transforms' % DS_NS)
    etree.SubElement(t2, '{%s}Transform' % DS_NS,
                     Algorithm=C14N_ALG)
    etree.SubElement(ref2, '{%s}DigestMethod' % DS_NS,
                     Algorithm=SHA256_ALG)
    etree.SubElement(
        ref2, '{%s}DigestValue' % DS_NS,
    ).text = to_digest

    # Firmar SignedInfo
    si_c14n = _c14n(si)
    sig_value = etree.SubElement(sig, '{%s}SignatureValue' % DS_NS)
    sig_value.text = _sign(private_key, si_c14n)

    # KeyInfo con ThumbprintReference
    ki = etree.SubElement(sig, '{%s}KeyInfo' % DS_NS)
    str_ref = etree.SubElement(
        ki, '{%s}SecurityTokenReference' % WSSE_NS,
    )
    ref = etree.SubElement(str_ref, '{%s}KeyIdentifier' % WSSE_NS)
    ref.set('ValueType', THUMBPRINT_TYPE)
    ref.set('EncodingType', ENCODING_TYPE)
    ref.text = cert_thumbprint

    return etree.tostring(env, xml_declaration=True, encoding='UTF-8')


# =====================================================================
# Utilidades de empaquetado y parseo
# =====================================================================

def _create_zip(xml_files: dict[str, bytes]) -> bytes:
    """Crea un archivo ZIP en memoria con los XMLs dados.

    Args:
        xml_files: Diccionario {nombre_archivo: contenido_bytes}.

    Returns:
        Contenido del ZIP como bytes.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in xml_files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _parse_response(text: str | bytes) -> dict:
    """Parsea respuesta SOAP de la DIAN.

    Extrae campos relevantes del XML de respuesta DIAN como
    StatusCode, StatusDescription, ZipKey, ErrorMessages, etc.

    Args:
        text: Texto XML de la respuesta SOAP.

    Returns:
        Diccionario con los campos extraídos de la respuesta.
    """
    raw = text.encode('utf-8') if isinstance(text, str) else text
    try:
        # Las respuestas son datos no confiables del proveedor.  No permitir
        # DTD, entidades externas ni acceso a red al inspeccionarlas.
        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False,
            dtd_validation=False, huge_tree=False,
        )
        root = etree.fromstring(raw, parser=parser)
    except Exception as e:
        return {
            'StatusCode': 'PARSE_ERROR',
            'ErrorMessage': str(e),
            'RawResponse': raw,
            'DianResponses': [],
        }

    result = {'DianResponses': []}
    targets = {
        'StatusCode', 'StatusDescription', 'StatusMessage',
        'ZipKey', 'IsValid', 'ErrorMessage',
        'ErrorMessageList', 'XmlDocumentComment',
        'XmlBase64Bytes', 'XmlFileName', 'XmlDocumentKey',
    }

    def local_name(elem):
        return etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ''

    def response_values(node):
        """Obtiene un DianResponse completo sin mezclar sus hermanos."""
        values = {'ErrorMessages': []}
        for elem in node.iter():
            tag = local_name(elem)
            if tag not in targets:
                continue
            if tag in ('ErrorMessageList', 'ErrorMessage'):
                direct = (elem.text or '').strip()
                if direct:
                    values['ErrorMessages'].append(direct)
                values['ErrorMessages'].extend(
                    value.text.strip() for value in elem.iter()
                    if value is not elem and value.text and value.text.strip()
                )
            elif tag == 'XmlBase64Bytes':
                encoded = elem.text or ''
                try:
                    values['ApplicationResponse'] = base64.b64decode(
                        encoded, validate=True
                    ).decode('utf-8', errors='replace')
                except Exception:
                    # Conservar el contenido íntegro, incluso si DIAN lo
                    # entrega mal codificado; el historial lo necesita.
                    values['ApplicationResponse'] = encoded
            else:
                values[tag] = elem.text or ''
        return values

    # GetStatusZip puede devolver varios DianResponse. Cada uno debe seguir
    # siendo una unidad independiente: el último IsValid no representa al lote.
    faults = [elem for elem in root.iter() if local_name(elem) == 'Fault']
    if faults:
        result['SOAPFault'] = True
        result['FaultDetails'] = [
            elem.text.strip() for fault in faults for elem in fault.iter()
            if elem.text and elem.text.strip()
        ]
        result['RawResponse'] = raw
        return result
    nodes = [elem for elem in root.iter() if local_name(elem) == 'DianResponse']
    if nodes:
        result['DianResponses'] = [response_values(node) for node in nodes]
    else:
        result['DianResponses'] = [response_values(root)]

    # Metadatos del sobre/lote: se extraen sin convertir el último resultado
    # individual en un resultado global. Mantiene compatibilidad de respuestas
    # síncronas de un solo documento.
    for elem in root.iter():
        tag = local_name(elem)
        if tag in ('ZipKey', 'StatusCode', 'StatusDescription', 'StatusMessage',
                   'ErrorMessage', 'XmlFileName', 'XmlDocumentKey') and elem.text:
            result.setdefault(tag, elem.text)
    if len(result['DianResponses']) == 1:
        only = result['DianResponses'][0]
        for key, value in only.items():
            if key != 'ErrorMessages':
                result.setdefault(key, value)
        if only.get('ErrorMessages'):
            result['ErrorMessages'] = only['ErrorMessages']

    if not nodes and not any(result['DianResponses'][0].values()):
        for elem in root.iter():
            tag = etree.QName(elem.tag).localname
            if tag in ('Text', 'Reason', 'faultstring',
                       'Value', 'Subcode'):
                t = elem.text
                if t and t.strip():
                    result.setdefault('FaultDetails', []).append(
                        t.strip())

    # SIEMPRE conservar el payload íntegro. La UI puede mostrar un resumen,
    # pero la evidencia persistente nunca se trunca.
    result['RawResponse'] = raw

    return result


_UBL_CAC_CBC_NS = {
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
}


def _parse_application_response_safely(application_response: str | bytes):
    if not application_response:
        return None
    raw = (application_response.encode('utf-8')
           if isinstance(application_response, str) else application_response)
    try:
        return etree.fromstring(raw, etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False,
            dtd_validation=False,
        ))
    except (ValueError, etree.XMLSyntaxError):
        return None


def extract_document_cunes(application_response: str | bytes) -> set[str]:
    """Extrae el CUNE/CUFE real del documento original referenciado.

    AUD-DIAN-34 (2026-10-04): evidencia real (respuesta GetStatusZip
    AUTORIZADA de la DIAN, StatusCode 00, nómina "SME-10") confirma que el
    identificador real del documento original es
    ``cac:DocumentResponse/cac:DocumentReference/cbc:UUID`` (visto con
    ``schemeName="CUFE-SHA384"``; el equivalente de nómina sería
    "CUNE-SHA384") -- NO ``cbc:ID``, que es el NÚMERO de negocio del
    documento (ver ``extract_document_numbers``). Antes esta función leía
    ``cbc:ID`` creyendo que era el CUNE, por lo que nunca emparejaba nada.
    El ``UUID``/``ID`` de nivel raíz del propio ApplicationResponse
    (identidad de la respuesta de DIAN, no del documento referenciado)
    sigue excluido por diseño -- solo cuenta la ruta UBL completa.
    """
    root = _parse_application_response_safely(application_response)
    if root is None:
        return set()
    return {
        element.text.strip() for element in root.xpath(
            './/cac:DocumentResponse/cac:DocumentReference/cbc:UUID',
            namespaces=_UBL_CAC_CBC_NS,
        ) if element.text and element.text.strip()
    }


def extract_document_numbers(application_response: str | bytes) -> set[str]:
    """Extrae el NÚMERO de negocio del documento original (NO es el CUNE).

    ``cac:DocumentResponse/cac:DocumentReference/cbc:ID`` -- ej.
    "NE0000000009", o "SME10" en el ejemplo real visto. Solo sirve para
    emparejar contra ``hr.payslip.l10n_co_ne_consecutive`` cuando DIAN no
    entrega CUNE (ver ``extract_document_cunes``) y el resultado es
    inequívoco dentro del manifiesto del ZipKey.
    """
    root = _parse_application_response_safely(application_response)
    if root is None:
        return set()
    return {
        element.text.strip() for element in root.xpath(
            './/cac:DocumentResponse/cac:DocumentReference/cbc:ID',
            namespaces=_UBL_CAC_CBC_NS,
        ) if element.text and element.text.strip()
    }


# =====================================================================
# Envío SOAP
# =====================================================================

def _send(
    action: str,
    endpoint: str,
    body_xml: str,
    cert_der: bytes,
    private_key,
) -> dict:
    """Envía un sobre SOAP firmado a la DIAN.

    Args:
        action: SOAP Action URL.
        endpoint: URL del web service DIAN.
        body_xml: Cuerpo XML como string.
        cert_der: Certificado en formato DER.
        private_key: Clave privada RSA.

    Returns:
        Diccionario con la respuesta parseada.
    """
    envelope = _build_envelope(
        action, endpoint, body_xml, cert_der, private_key,
    )
    # La evidencia debe ser el sobre completo realmente transmitido.
    raw_request = envelope

    headers = {
        'Content-Type': (
            'application/soap+xml;charset=UTF-8;'
            'action="%s"' % action
        ),
    }

    _logger.info("DIAN SOAP to %s", endpoint)

    try:
        resp = requests.post(
            endpoint, data=envelope, headers=headers,
            timeout=SOAP_TIMEOUT, verify=True,
        )

        _logger.info("DIAN HTTP %d (%d bytes)", resp.status_code, len(resp.content))

        if resp.status_code >= 400:
            _logger.error("DIAN HTTP error %d", resp.status_code)
            result = _parse_response(resp.content)
            result['HttpStatus'] = resp.status_code
            if not result.get('StatusCode'):
                result['StatusCode'] = str(resp.status_code)
            faults = result.get('FaultDetails', [])
            if faults:
                result['ErrorMessage'] = ' | '.join(faults)
            elif not result.get('ErrorMessage'):
                result['ErrorMessage'] = (
                    'HTTP %d: %s' % (resp.status_code,
                                     'respuesta no SOAP')
                )
            result['RawRequest'] = raw_request
            return result

    except requests.RequestException as e:
        _logger.error("DIAN connection: %s", e)
        return {
            'StatusCode': 'CONNECTION_ERROR',
            'ErrorMessage': str(e),
            'TransportError': str(e),
            'RawRequest': raw_request,
        }

    result = _parse_response(resp.content)
    result['HttpStatus'] = resp.status_code
    result['RawRequest'] = raw_request
    return result


# =====================================================================
# Operaciones públicas de nómina electrónica
# =====================================================================

def send_nomina_sync(
    xml_bytes: bytes,
    filename: str,
    private_key=None,
    cert_pem: Optional[bytes] = None,
    cert_der_b64: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> dict:
    """Envía un documento de nómina individual de forma síncrona.

    Usa la operación SendNominaSync de la DIAN para obtener la
    respuesta de validación inmediata.

    Args:
        xml_bytes: XML de nómina firmado como bytes.
        filename: Nombre del archivo XML (ej: 'ne_NE001.xml').
        private_key: Clave privada RSA del certificado.
        cert_pem: Certificado PEM como bytes (alternativa a cert_der_b64).
        cert_der_b64: Certificado DER en base64 (alternativa a cert_pem).
        endpoint: URL del endpoint DIAN. Si None, usa habilitación.

    Returns:
        Diccionario con la respuesta de la DIAN.
    """
    if not endpoint:
        endpoint = DIAN_ENDPOINT_HAB

    if cert_pem and not cert_der_b64:
        cert = x509.load_pem_x509_certificate(cert_pem)
        cert_der = cert.public_bytes(serialization.Encoding.DER)
    elif cert_der_b64:
        cert_der = base64.b64decode(cert_der_b64)
    else:
        return {'StatusCode': 'ERROR',
                'ErrorMessage': 'No se proporcionó certificado'}

    # Crear ZIP con un solo archivo
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, xml_bytes)
    zip_bytes = buf.getvalue()
    zip_b64 = base64.b64encode(zip_bytes).decode('ascii')
    zip_name = filename.replace('.xml', '.zip')

    body_xml = (
        '<wcf:SendNominaSync xmlns:wcf="{ns}">'
        '<wcf:fileName>{fn}</wcf:fileName>'
        '<wcf:contentFile>{ct}</wcf:contentFile>'
        '</wcf:SendNominaSync>'
    ).format(ns=WCF_NS, fn=zip_name, ct=zip_b64)

    _logger.info("SendNominaSync: %s (%d bytes)",
                 filename, len(zip_bytes))

    return _send(
        SOAP_ACTION_SEND_NOMINA, endpoint,
        body_xml, cert_der, private_key,
    )


def send_test_set_async(
    xml_files: dict[str, bytes],
    test_set_id: str,
    private_key=None,
    cert_pem: Optional[bytes] = None,
    cert_der_b64: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> dict:
    """Envía el set de pruebas de nómina electrónica a la DIAN.

    Args:
        xml_files: Diccionario {nombre_archivo: contenido_xml_bytes}.
        test_set_id: Identificador del set de pruebas DIAN.
        private_key: Clave privada RSA del certificado.
        cert_pem: Certificado PEM como bytes (alternativa a cert_der_b64).
        cert_der_b64: Certificado DER en base64 (alternativa a cert_pem).
        endpoint: URL del endpoint DIAN. Si None, usa habilitación.

    Returns:
        Diccionario con la respuesta de la DIAN.
    """
    if not endpoint:
        endpoint = DIAN_ENDPOINT_HAB

    # Obtener cert_der del p12 si tenemos cert_pem
    if cert_pem and not cert_der_b64:
        cert = x509.load_pem_x509_certificate(cert_pem)
        cert_der = cert.public_bytes(serialization.Encoding.DER)
    elif cert_der_b64:
        cert_der = base64.b64decode(cert_der_b64)
    else:
        return {'StatusCode': 'ERROR',
                'ErrorMessage': 'No se proporcionó certificado'}

    zip_bytes = _create_zip(xml_files)
    zip_b64 = base64.b64encode(zip_bytes).decode('ascii')
    zip_name = 'test_set_%s.zip' % test_set_id[:8]

    body_xml = (
        '<wcf:SendTestSetAsync xmlns:wcf="{ns}">'
        '<wcf:fileName>{fn}</wcf:fileName>'
        '<wcf:contentFile>{ct}</wcf:contentFile>'
        '<wcf:testSetId>{ts}</wcf:testSetId>'
        '</wcf:SendTestSetAsync>'
    ).format(ns=WCF_NS, fn=zip_name, ct=zip_b64, ts=test_set_id)

    _logger.info("SendTestSetAsync: %d files, %d bytes ZIP",
                 len(xml_files), len(zip_bytes))

    return _send(
        SOAP_ACTION_SEND_TEST_SET, endpoint,
        body_xml, cert_der, private_key,
    )


def get_status_zip(
    track_id: str,
    private_key=None,
    cert_pem: Optional[bytes] = None,
    cert_der_b64: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> dict:
    """Consulta el estado de un envío por su track ID.

    Args:
        track_id: Identificador de seguimiento del envío (ZipKey).
        private_key: Clave privada RSA del certificado.
        cert_pem: Certificado PEM como bytes.
        cert_der_b64: Certificado DER en base64.
        endpoint: URL del endpoint DIAN. Si None, usa habilitación.

    Returns:
        Diccionario con el estado del envío.
    """
    if not endpoint:
        endpoint = DIAN_ENDPOINT_HAB

    if cert_pem and not cert_der_b64:
        cert = x509.load_pem_x509_certificate(cert_pem)
        cert_der = cert.public_bytes(serialization.Encoding.DER)
    elif cert_der_b64:
        cert_der = base64.b64decode(cert_der_b64)
    else:
        return {'StatusCode': 'ERROR',
                'ErrorMessage': 'No se proporcionó certificado'}

    body_xml = (
        '<wcf:GetStatusZip xmlns:wcf="{ns}">'
        '<wcf:trackId>{tid}</wcf:trackId>'
        '</wcf:GetStatusZip>'
    ).format(ns=WCF_NS, tid=track_id)

    return _send(
        SOAP_ACTION_GET_STATUS, endpoint,
        body_xml, cert_der, private_key,
    )
