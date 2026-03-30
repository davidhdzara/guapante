"""Firmador XML XAdES-BES para documentos DIAN.

Lee el certificado .p12 y aplica firma XAdES-BES a cada XML UBL.
Compatible con los requisitos del Anexo Técnico DIAN.
"""

import base64
import hashlib
import logging
import uuid
from datetime import datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import pkcs12

from lxml import etree

from . import test_data as td

_logger = logging.getLogger(__name__)


def load_p12(p12_bytes, password):
    """Extrae private key y certificado PEM de un archivo .p12.

    Args:
        p12_bytes: Contenido binario del archivo .p12
        password: Contraseña del certificado (str o bytes)

    Returns:
        tuple: (private_key, certificate_pem_bytes, cert_object)
    """
    if isinstance(password, str):
        password = password.encode('utf-8')

    private_key, certificate, _ = pkcs12.load_key_and_certificates(
        p12_bytes, password, default_backend(),
    )

    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    cert_der = certificate.public_bytes(serialization.Encoding.DER)

    return private_key, cert_pem, cert_der, certificate


def _compute_digest(data):
    """Calcula SHA-256 digest en base64."""
    digest = hashlib.sha256(data).digest()
    return base64.b64encode(digest).decode('ascii')


def _sign_data(private_key, data):
    """Firma datos con RSA + SHA-256."""
    signature = private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode('ascii')


def sign_xml(xml_bytes, p12_bytes, p12_password):
    """Firma un XML UBL 2.1 con XAdES-BES.

    Agrega la firma digital en la segunda UBLExtension del documento.

    Args:
        xml_bytes: XML como bytes
        p12_bytes: Archivo .p12 como bytes
        p12_password: Contraseña del .p12

    Returns:
        bytes: XML firmado como bytes UTF-8
    """
    private_key, cert_pem, cert_der, cert_obj = load_p12(
        p12_bytes, p12_password,
    )

    # Parse XML
    root = etree.fromstring(xml_bytes)
    ns_ext = td.NS['ext']
    ns_ds = td.NS['ds']
    ns_xades = td.NS['xades']

    # Encontrar la segunda extension (placeholder para firma)
    extensions = root.find('{%s}UBLExtensions' % ns_ext)
    ext_list = extensions.findall('{%s}UBLExtension' % ns_ext)

    if len(ext_list) < 2:
        raise ValueError(
            "XML must have at least 2 UBLExtensions for signing"
        )

    sig_extension = ext_list[1].find(
        '{%s}ExtensionContent' % ns_ext,
    )

    # IDs únicos
    sig_id = 'xmldsig-%s' % uuid.uuid4().hex[:8]
    ref_id = '%s-ref0' % sig_id
    kinfo_id = '%s-keyinfo' % sig_id
    sp_id = '%s-sigprops' % sig_id

    # Certificado en base64
    cert_b64 = base64.b64encode(cert_der).decode('ascii')

    # Certificate digest
    cert_digest = _compute_digest(cert_der)

    # Certificate issuer info
    issuer_name = cert_obj.issuer.rfc4514_string()
    serial_number = str(cert_obj.serial_number)

    # Calcular digest del documento (sin la firma)
    doc_xml = etree.tostring(root, method='c14n')
    doc_digest = _compute_digest(doc_xml)

    # Build Signature element
    sig = etree.SubElement(
        sig_extension, '{%s}Signature' % ns_ds, Id=sig_id,
    )

    # SignedInfo
    signed_info = etree.SubElement(sig, '{%s}SignedInfo' % ns_ds)

    c14n_method = etree.SubElement(
        signed_info, '{%s}CanonicalizationMethod' % ns_ds,
        Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315',
    )

    sig_method = etree.SubElement(
        signed_info, '{%s}SignatureMethod' % ns_ds,
        Algorithm='http://www.w3.org/2001/04/xmldsig-more'
                  '#rsa-sha256',
    )

    # Reference to document
    ref = etree.SubElement(
        signed_info, '{%s}Reference' % ns_ds,
        Id=ref_id, URI='',
    )
    transforms = etree.SubElement(ref, '{%s}Transforms' % ns_ds)
    etree.SubElement(
        transforms, '{%s}Transform' % ns_ds,
        Algorithm='http://www.w3.org/2000/09/xmldsig'
                  '#enveloped-signature',
    )
    digest_method = etree.SubElement(
        ref, '{%s}DigestMethod' % ns_ds,
        Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
    )
    digest_value = etree.SubElement(
        ref, '{%s}DigestValue' % ns_ds,
    )
    digest_value.text = doc_digest

    # Reference to KeyInfo
    ref_ki = etree.SubElement(
        signed_info, '{%s}Reference' % ns_ds,
        URI='#%s' % kinfo_id,
    )
    dm_ki = etree.SubElement(
        ref_ki, '{%s}DigestMethod' % ns_ds,
        Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
    )

    # Reference to SignedProperties
    ref_sp = etree.SubElement(
        signed_info, '{%s}Reference' % ns_ds,
        Type='http://uri.etsi.org/01903#SignedProperties',
        URI='#%s' % sp_id,
    )
    dm_sp = etree.SubElement(
        ref_sp, '{%s}DigestMethod' % ns_ds,
        Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
    )

    # SignatureValue placeholder
    sig_value = etree.SubElement(sig, '{%s}SignatureValue' % ns_ds)

    # KeyInfo
    key_info = etree.SubElement(
        sig, '{%s}KeyInfo' % ns_ds, Id=kinfo_id,
    )
    x509_data = etree.SubElement(
        key_info, '{%s}X509Data' % ns_ds,
    )
    x509_cert = etree.SubElement(
        x509_data, '{%s}X509Certificate' % ns_ds,
    )
    x509_cert.text = cert_b64

    # Object > QualifyingProperties > SignedProperties (XAdES)
    obj = etree.SubElement(sig, '{%s}Object' % ns_ds)
    qp = etree.SubElement(
        obj, '{%s}QualifyingProperties' % ns_xades,
        Target='#%s' % sig_id,
    )
    signed_props = etree.SubElement(
        qp, '{%s}SignedProperties' % ns_xades, Id=sp_id,
    )

    # SignedSignatureProperties
    ssp = etree.SubElement(
        signed_props,
        '{%s}SignedSignatureProperties' % ns_xades,
    )
    signing_time = etree.SubElement(
        ssp, '{%s}SigningTime' % ns_xades,
    )
    signing_time.text = datetime.now().strftime(
        '%Y-%m-%dT%H:%M:%S-05:00'
    )

    # SigningCertificate
    signing_cert = etree.SubElement(
        ssp, '{%s}SigningCertificate' % ns_xades,
    )
    cert_elem = etree.SubElement(
        signing_cert, '{%s}Cert' % ns_xades,
    )
    cert_digest_elem = etree.SubElement(
        cert_elem, '{%s}CertDigest' % ns_xades,
    )
    etree.SubElement(
        cert_digest_elem, '{%s}DigestMethod' % ns_ds,
        Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
    )
    cert_dv = etree.SubElement(
        cert_digest_elem, '{%s}DigestValue' % ns_ds,
    )
    cert_dv.text = cert_digest

    issuer_serial = etree.SubElement(
        cert_elem, '{%s}IssuerSerial' % ns_xades,
    )
    x509_issuer = etree.SubElement(
        issuer_serial, '{%s}X509IssuerName' % ns_ds,
    )
    x509_issuer.text = issuer_name
    x509_serial = etree.SubElement(
        issuer_serial, '{%s}X509SerialNumber' % ns_ds,
    )
    x509_serial.text = serial_number

    # SignaturePolicyIdentifier
    spi = etree.SubElement(
        ssp, '{%s}SignaturePolicyIdentifier' % ns_xades,
    )
    sp_elem = etree.SubElement(
        spi, '{%s}SignaturePolicyId' % ns_xades,
    )
    sp_id_elem = etree.SubElement(
        sp_elem, '{%s}SigPolicyId' % ns_xades,
    )
    sp_identifier = etree.SubElement(
        sp_id_elem, '{%s}Identifier' % ns_xades,
    )
    sp_identifier.text = (
        'https://facturaelectronica.dian.gov.co/politicadefirma'
        '/v2/politicadefirmav2.pdf'
    )
    sp_hash = etree.SubElement(
        sp_elem, '{%s}SigPolicyHash' % ns_xades,
    )
    etree.SubElement(
        sp_hash, '{%s}DigestMethod' % ns_ds,
        Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
    )
    sp_hash_dv = etree.SubElement(
        sp_hash, '{%s}DigestValue' % ns_ds,
    )
    sp_hash_dv.text = (
        'dMoMvtcG5aIzgYo0tIsSQeVJBDnUnfSOfBpxXrmor0Y='
    )

    # SignerRole
    signer_role = etree.SubElement(
        ssp, '{%s}SignerRole' % ns_xades,
    )
    claimed = etree.SubElement(
        signer_role, '{%s}ClaimedRoles' % ns_xades,
    )
    role = etree.SubElement(
        claimed, '{%s}ClaimedRole' % ns_xades,
    )
    role.text = 'supplier'

    # Now compute the digests for KeyInfo and SignedProperties
    ki_c14n = etree.tostring(key_info, method='c14n')
    ki_digest = _compute_digest(ki_c14n)

    sp_c14n = etree.tostring(signed_props, method='c14n')
    sp_digest = _compute_digest(sp_c14n)

    # Fill in the digests
    dv_ki = etree.SubElement(ref_ki, '{%s}DigestValue' % ns_ds)
    dv_ki.text = ki_digest

    dv_sp = etree.SubElement(ref_sp, '{%s}DigestValue' % ns_ds)
    dv_sp.text = sp_digest

    # Sign the SignedInfo
    si_c14n = etree.tostring(signed_info, method='c14n')
    signature_value = _sign_data(private_key, si_c14n)
    sig_value.text = signature_value

    return etree.tostring(
        root, xml_declaration=True, encoding='UTF-8',
        pretty_print=True,
    )
