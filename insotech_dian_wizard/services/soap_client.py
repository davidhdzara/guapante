"""Cliente SOAP para los web services de la DIAN.

Implementa las operaciones necesarias para el set de pruebas:
- SendTestSetAsync: enviar set de pruebas
- GetStatusZip: consultar estado de un envío

Usa SOAP 1.2 + WS-Addressing + WS-Security con:
- TransportBinding (HTTPS)
- EndorsingSupportingTokens (X509 endorsa Timestamp)
- ThumbprintReference para el key identifier
- Firma wsa:To + Timestamp
- AlgorithmSuite: Basic256Sha256Rsa15
"""

import base64
import hashlib
import io
import logging
import uuid
import zipfile
from datetime import datetime, timedelta

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

from . import test_data as td

_logger = logging.getLogger(__name__)

SOAP_TIMEOUT = 45

# Namespaces
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
WCF_NS = 'http://wcf.dian.colombia'

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

# Algorithms (Basic256Sha256Rsa15)
C14N_ALG = 'http://www.w3.org/2001/10/xml-exc-c14n#'
SHA256_ALG = 'http://www.w3.org/2001/04/xmlenc#sha256'
RSA_SHA256_ALG = (
    'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
)


def _c14n(elem):
    """Exclusive C14N de un elemento."""
    return etree.tostring(elem, method='c14n', exclusive=True)


def _sha256_b64(data):
    """SHA-256 digest en base64."""
    return base64.b64encode(
        hashlib.sha256(data).digest()
    ).decode('ascii')


def _sha1_b64(data):
    """SHA-1 digest en base64 (para thumbprint)."""
    return base64.b64encode(
        hashlib.sha1(data).digest()
    ).decode('ascii')


def _sign(private_key, data):
    """Firma RSA-SHA256."""
    sig = private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode('ascii')


def _build_envelope(action, endpoint, body_xml,
                    cert_der, private_key):
    """Construye SOAP 1.2 con WS-Security (TransportBinding +
    EndorsingSupportingTokens).

    La política de la DIAN requiere:
    - TransportBinding con HTTPS (sin firmar Body)
    - EndorsingSupportingTokens: X509 que endosa el Timestamp
    - SignedParts: wsa:To header
    - ThumbprintReference para key identifier
    """
    now = datetime.utcnow()
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

    # Build XML tree
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
    str_ref = etree.SubElement(ki, '{%s}SecurityTokenReference' % WSSE_NS)
    ref = etree.SubElement(str_ref, '{%s}KeyIdentifier' % WSSE_NS)
    ref.set('ValueType', THUMBPRINT_TYPE)
    ref.set('EncodingType', ENCODING_TYPE)
    ref.text = cert_thumbprint

    return etree.tostring(env, xml_declaration=True, encoding='UTF-8')


def _create_zip(xml_files):
    """Crea un ZIP en memoria."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in xml_files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _parse_response(text):
    """Parsea respuesta SOAP de la DIAN."""
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


def _send(action, endpoint, body_xml, cert_der, private_key):
    """Envía SOAP firmado a la DIAN."""
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


def send_test_set_async(xml_files, test_set_id,
                        private_key=None, cert_pem=None,
                        cert_der_b64=None, endpoint=None):
    """Envía el set de pruebas a la DIAN."""
    if not endpoint:
        endpoint = td.DIAN_ENDPOINT_HAB

    # Obtener cert_der del p12 si tenemos cert_pem
    if cert_pem and not cert_der_b64:
        from cryptography import x509
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
        td.SOAP_ACTION_SEND_TEST_SET, endpoint,
        body_xml, cert_der, private_key,
    )


def get_status_zip(track_id, private_key=None,
                   cert_pem=None, cert_der_b64=None,
                   endpoint=None):
    """Consulta estado de un envío."""
    if not endpoint:
        endpoint = td.DIAN_ENDPOINT_HAB

    if cert_pem and not cert_der_b64:
        from cryptography import x509
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
        td.SOAP_ACTION_GET_STATUS, endpoint,
        body_xml, cert_der, private_key,
    )


def send_bill_sync(xml_bytes, filename,
                   private_key=None, cert_pem=None,
                   endpoint=None):
    """Envía UN documento individual de forma síncrona.

    Usa SendBillSync para obtener errores de validación EXACTOS
    que SendTestSetAsync enmascara.
    """
    if not endpoint:
        endpoint = td.DIAN_ENDPOINT_HAB

    if cert_pem:
        from cryptography import x509
        cert = x509.load_pem_x509_certificate(cert_pem)
        cert_der = cert.public_bytes(serialization.Encoding.DER)
    else:
        return {'StatusCode': 'ERROR',
                'ErrorMessage': 'No se proporcionó certificado'}

    # Crear ZIP con UN solo archivo
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, xml_bytes)
    zip_bytes = buf.getvalue()
    zip_b64 = base64.b64encode(zip_bytes).decode('ascii')
    zip_name = filename.replace('.xml', '.zip')

    body_xml = (
        '<wcf:SendBillSync xmlns:wcf="{ns}">'
        '<wcf:fileName>{fn}</wcf:fileName>'
        '<wcf:contentFile>{ct}</wcf:contentFile>'
        '</wcf:SendBillSync>'
    ).format(ns=WCF_NS, fn=zip_name, ct=zip_b64)

    _logger.info("SendBillSync: %s (%d bytes)",
                 filename, len(zip_bytes))

    return _send(
        td.SOAP_ACTION_SEND_BILL, endpoint,
        body_xml, cert_der, private_key,
    )
