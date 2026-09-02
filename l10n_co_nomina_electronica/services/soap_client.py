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
    try:
        raw = text.encode('utf-8') if isinstance(text, str) else text
        root = etree.fromstring(raw)
    except Exception as e:
        return {
            'StatusCode': 'PARSE_ERROR',
            'ErrorMessage': str(e),
            'RawResponse': str(text)[:3000],
        }

    result = {}
    targets = {
        'StatusCode', 'StatusDescription', 'StatusMessage',
        'ZipKey', 'IsValid', 'ErrorMessage',
        'ErrorMessageList', 'XmlDocumentComment',
        'XmlBase64Bytes', 'XmlFileName',
    }

    for elem in root.iter():
        tag = etree.QName(elem.tag).localname
        if tag in targets:
            if tag == 'ErrorMessageList':
                msgs = [s.text for s in elem.iter()
                        if s.text and s.text.strip()]
                result['ErrorMessages'] = msgs
            elif tag == 'XmlDocumentComment':
                # Application Response con detalles
                result['XmlDocumentComment'] = elem.text or ''
            elif tag == 'XmlBase64Bytes':
                # XML de respuesta codificado en base64
                try:
                    if elem.text:
                        decoded = base64.b64decode(
                            elem.text).decode(
                                'utf-8', errors='replace')
                        result['ApplicationResponse'] = (
                            decoded[:5000])
                except Exception:
                    result['ApplicationResponse'] = (
                        str(elem.text or '')[:500])
            else:
                result[tag] = elem.text or ''

    if not result:
        for elem in root.iter():
            tag = etree.QName(elem.tag).localname
            if tag in ('Text', 'Reason', 'faultstring',
                       'Value', 'Subcode'):
                t = elem.text
                if t and t.strip():
                    result.setdefault('FaultDetails', []).append(
                        t.strip())

    # SIEMPRE incluir la respuesta raw para debug
    result['RawResponse'] = str(text)[:5000]

    return result


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

        _logger.info("DIAN HTTP %d (%d bytes)",
                      resp.status_code, len(resp.text))

        if resp.status_code >= 400:
            _logger.error("DIAN error: %s", resp.text[:2000])
            result = _parse_response(resp.text)
            if not result.get('StatusCode'):
                result['StatusCode'] = str(resp.status_code)
            faults = result.get('FaultDetails', [])
            if faults:
                result['ErrorMessage'] = ' | '.join(faults)
            elif not result.get('ErrorMessage'):
                result['ErrorMessage'] = (
                    'HTTP %d: %s' % (resp.status_code,
                                     resp.text[:300])
                )
            return result

    except requests.RequestException as e:
        _logger.error("DIAN connection: %s", e)
        return {
            'StatusCode': 'CONNECTION_ERROR',
            'ErrorMessage': str(e),
        }

    return _parse_response(resp.text)


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
