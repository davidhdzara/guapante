"""Firmador XML XAdES-BES para documentos de Nómina Electrónica DIAN.

Lee el certificado .p12 y aplica firma XAdES-BES a cada XML de nómina.
Compatible con los requisitos del Anexo Técnico de Nómina Electrónica DIAN.

Adaptado de insotech_dian_wizard/services/xml_signer.py para nómina
electrónica, sin dependencias de Odoo ni de test_data.

Dependencias externas:
    - cryptography (pip install cryptography)
    - lxml (pip install lxml)
"""

import base64
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Optional

from pytz import timezone as _pytz_timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

from lxml import etree

_logger = logging.getLogger(__name__)

# =====================================================================
# Namespaces — definidos inline (sin dependencia de test_data)
# =====================================================================

NS_DS = 'http://www.w3.org/2000/09/xmldsig#'
NS_EXT = (
    'urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonExtensionComponents-2'
)
NS_XADES = 'http://uri.etsi.org/01903/v1.3.2#'
NS_XADES141 = 'http://uri.etsi.org/01903/v1.4.1#'

# Namespace del documento de nómina individual
NS_NOMINA = 'dian:gov:co:facturaelectronica:NominaIndividual'
NS_NOMINA_AJUSTE = (
    'dian:gov:co:facturaelectronica:NominaIndividualDeAjuste'
)

# Política de firma DIAN v2
SIGNATURE_POLICY_URL = (
    'https://facturaelectronica.dian.gov.co/politicadefirma'
    '/v2/politicadefirmav2.pdf'
)
SIGNATURE_POLICY_DIGEST = 'dMoMvtcG5aIzgYo0tIsSQeVJBDnUnfSOfBpxXrmor0Y='


# =====================================================================
# Carga de certificado desde certificate.certificate nativo
# =====================================================================

def load_from_certificate(certificate) -> tuple:
    """Extrae private key y certificado PEM/DER de un certificate.certificate nativo.

    A diferencia del antiguo esquema .p12, no hay contraseña PKCS12 que
    desempaquetar -- pero ``pem_key`` y ``pem_certificate`` siguen siendo
    campos Binary base64-encoded (confirmado en
    ``certificate/models/key.py``/``certificate.py``), así que igual hace
    falta ``base64.b64decode()`` sobre ambos. ``with_context(bin_size=False)``
    replica el patrón que usa el propio módulo ``certificate`` para evitar
    que el ORM devuelva el placeholder de tamaño en vez del contenido real.

    AUD-DIAN-34 (2026-10-04, DC25): además de la hoja, resuelve la cadena
    completa (hoja + intermedia + raíz) vía el método nativo
    ``certificate._get_certificate_chain()`` -- el modelo genérico
    ``certificate.certificate`` ya la arma sola al cargar el .p12
    (enlazando cada eslabón por ``issuer_cert_id``), mismo dato que usa
    ``account_edi_xml_ubl_dian.py`` (Facturación Electrónica nativa, en
    producción) para construir sus 3 ``xades:Cert``. DC25 exige al menos
    3 grupos ``Cert`` dentro de ``SigningCertificate`` -- antes esta
    función solo devolvía la hoja, dejando a ``sign_xml`` sin forma de
    construir los otros 2.

    Args:
        certificate: recordset certificate.certificate (un solo registro,
            la hoja/certificado de firma).

    Returns:
        Tupla (private_key, cert_pem_bytes, cert_der_bytes, cert_object,
        chain_cert_objects) -- el último es la lista de objetos
        ``x509.Certificate`` de la cadena completa, hoja primero.
    """
    certificate.ensure_one()
    cert = certificate.with_context(bin_size=False)
    key = cert.private_key_id.with_context(bin_size=False)

    pem_key_bytes = base64.b64decode(key.pem_key)
    pem_cert_bytes = base64.b64decode(cert.pem_certificate)

    private_key = serialization.load_pem_private_key(
        pem_key_bytes, password=None, backend=default_backend(),
    )
    cert_obj = x509.load_pem_x509_certificate(pem_cert_bytes, default_backend())
    cert_pem = cert_obj.public_bytes(serialization.Encoding.PEM)
    cert_der = cert_obj.public_bytes(serialization.Encoding.DER)

    chain_records = cert._get_certificate_chain()
    chain_cert_objects = [
        x509.load_pem_x509_certificate(
            base64.b64decode(
                chain_cert.with_context(bin_size=False).pem_certificate
            ),
            default_backend(),
        )
        for chain_cert in chain_records
    ]
    if not chain_cert_objects:
        # Nunca debería pasar (la hoja misma siempre forma parte de su
        # propia cadena) -- si pasa, no hay cadena resuelta y es mejor
        # fallar explícito que firmar con un solo Cert (DC25 lo rechaza).
        raise ValueError(
            'No se pudo resolver la cadena de certificación (hoja + '
            'intermedia + raíz) para %s -- _get_certificate_chain() '
            'devolvió vacío.' % certificate.display_name
        )

    return private_key, cert_pem, cert_der, cert_obj, chain_cert_objects


# =====================================================================
# Funciones auxiliares de criptografía
# =====================================================================

def _compute_digest(data: bytes) -> str:
    """Calcula SHA-256 digest en base64.

    Args:
        data: Datos binarios a digerir.

    Returns:
        Digest SHA-256 codificado en base64.
    """
    digest = hashlib.sha256(data).digest()
    return base64.b64encode(digest).decode('ascii')


def _sign_data(private_key, data: bytes) -> str:
    """Firma datos con RSA + SHA-256 (PKCS1v15).

    Args:
        private_key: Clave privada RSA del certificado.
        data: Datos binarios a firmar.

    Returns:
        Firma codificada en base64.
    """
    signature = private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode('ascii')


# =====================================================================
# Firmado XAdES-BES del XML
# =====================================================================

def sign_xml(
    xml_bytes: bytes,
    private_key,
    cert_pem: bytes,
    cert_der: bytes,
    cert_obj,
    cert_chain=None,
) -> bytes:
    """Firma un XML de Nómina Electrónica con XAdES-BES.

    Agrega la firma digital en el elemento UBLExtensions del documento.
    Compatible tanto con NominaIndividual como con
    NominaIndividualDeAjuste.

    El proceso de firma sigue los pasos:
    1. Parsear XML y ubicar UBLExtensions
    2. Crear UBLExtension con ExtensionContent como placeholder
    3. Construir la estructura ds:Signature con:
       - SignedInfo (references al documento, KeyInfo y SignedProperties)
       - SignatureValue
       - KeyInfo con certificado X.509 (solo la hoja)
       - Object > QualifyingProperties > SignedProperties (XAdES), con
         un xades:Cert por cada certificado de ``cert_chain``
    4. Calcular digests y firmar

    El material de firma ya debe estar cargado (ver ``load_from_certificate``)
    -- esta función no sabe de dónde viene el certificado, solo firma.

    Args:
        xml_bytes: XML de nómina como bytes.
        private_key: Clave privada RSA ya cargada.
        cert_pem: Certificado en formato PEM (bytes).
        cert_der: Certificado en formato DER (bytes).
        cert_obj: Objeto x509.Certificate ya cargado (la hoja).
        cert_chain: Lista de objetos x509.Certificate de la cadena
            completa (hoja + intermedia + raíz), hoja primero. DC25 del
            Anexo Técnico exige al menos 3 grupos ``xades:Cert`` dentro
            de ``SigningCertificate`` -- si se omite, se firma solo con
            la hoja (``[cert_obj]``), estructuralmente incompleto frente
            a DC25/DC37-DC46.

    Returns:
        XML firmado como bytes UTF-8 con declaración XML.

    Raises:
        ValueError: Si el XML no tiene UBLExtensions.
    """
    # Parsear XML
    root = etree.fromstring(xml_bytes)

    # Encontrar UBLExtensions (puede estar vacío o con extensiones)
    extensions = root.find('{%s}UBLExtensions' % NS_EXT)
    if extensions is None:
        raise ValueError(
            'El XML debe tener un elemento ext:UBLExtensions '
            'para inyectar la firma.'
        )

    # Crear una nueva UBLExtension para la firma
    ubl_ext = etree.SubElement(
        extensions, '{%s}UBLExtension' % NS_EXT,
    )
    sig_extension = etree.SubElement(
        ubl_ext, '{%s}ExtensionContent' % NS_EXT,
    )

    # IDs únicos para la firma
    sig_id = 'xmldsig-%s' % uuid.uuid4().hex[:8]
    ref_id = '%s-ref0' % sig_id
    kinfo_id = '%s-keyinfo' % sig_id
    sp_id = '%s-sigprops' % sig_id

    # Certificado en base64 (DER) -- solo la hoja, para ds:KeyInfo
    cert_b64 = base64.b64encode(cert_der).decode('ascii')

    # Cadena completa para xades:SigningCertificate/xades:Cert (DC25:
    # minimo 3 grupos Cert -- hoja + intermedia + raiz). Si no se pasa
    # cadena, cae a solo la hoja (estructuralmente incompleto, pero no
    # rompe la firma de documentos que no dependan de esto).
    chain = cert_chain or [cert_obj]

    # Calcular digest del documento (sin la firma aún)
    doc_xml = etree.tostring(root, method='c14n')
    doc_digest = _compute_digest(doc_xml)

    # ===== Construir elemento ds:Signature =====
    sig = etree.SubElement(
        sig_extension, '{%s}Signature' % NS_DS, Id=sig_id,
    )

    # --- SignedInfo ---
    signed_info = etree.SubElement(sig, '{%s}SignedInfo' % NS_DS)

    etree.SubElement(
        signed_info, '{%s}CanonicalizationMethod' % NS_DS,
        Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315',
    )

    etree.SubElement(
        signed_info, '{%s}SignatureMethod' % NS_DS,
        Algorithm='http://www.w3.org/2001/04/xmldsig-more'
                  '#rsa-sha256',
    )

    # Reference al documento completo
    ref = etree.SubElement(
        signed_info, '{%s}Reference' % NS_DS,
        Id=ref_id, URI='',
    )
    transforms = etree.SubElement(ref, '{%s}Transforms' % NS_DS)
    etree.SubElement(
        transforms, '{%s}Transform' % NS_DS,
        Algorithm='http://www.w3.org/2000/09/xmldsig'
                  '#enveloped-signature',
    )
    etree.SubElement(
        ref, '{%s}DigestMethod' % NS_DS,
        Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
    )
    digest_value = etree.SubElement(
        ref, '{%s}DigestValue' % NS_DS,
    )
    digest_value.text = doc_digest

    # Reference al KeyInfo
    ref_ki = etree.SubElement(
        signed_info, '{%s}Reference' % NS_DS,
        URI='#%s' % kinfo_id,
    )
    etree.SubElement(
        ref_ki, '{%s}DigestMethod' % NS_DS,
        Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
    )

    # Reference a SignedProperties
    ref_sp = etree.SubElement(
        signed_info, '{%s}Reference' % NS_DS,
        Type='http://uri.etsi.org/01903#SignedProperties',
        URI='#%s' % sp_id,
    )
    etree.SubElement(
        ref_sp, '{%s}DigestMethod' % NS_DS,
        Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
    )

    # --- SignatureValue (placeholder, se llena después) ---
    # AUD-DIAN-34 (2026-09-14): Id agregado para calzar con la
    # implementacion nativa de Facturacion Electronica (l10n_co_dian),
    # que siempre le pone Id a SignatureValue -- opcional segun XML-DSIG,
    # pero se iguala por si la DIAN lo espera.
    sig_value = etree.SubElement(
        sig, '{%s}SignatureValue' % NS_DS, Id='%s-sigvalue' % sig_id,
    )

    # --- KeyInfo ---
    key_info = etree.SubElement(
        sig, '{%s}KeyInfo' % NS_DS, Id=kinfo_id,
    )
    x509_data = etree.SubElement(
        key_info, '{%s}X509Data' % NS_DS,
    )
    x509_cert = etree.SubElement(
        x509_data, '{%s}X509Certificate' % NS_DS,
    )
    x509_cert.text = cert_b64

    # --- Object > QualifyingProperties > SignedProperties (XAdES) ---
    obj = etree.SubElement(sig, '{%s}Object' % NS_DS)
    qp = etree.SubElement(
        obj, '{%s}QualifyingProperties' % NS_XADES,
        Target='#%s' % sig_id,
    )
    signed_props = etree.SubElement(
        qp, '{%s}SignedProperties' % NS_XADES, Id=sp_id,
    )

    # SignedSignatureProperties
    ssp = etree.SubElement(
        signed_props,
        '{%s}SignedSignatureProperties' % NS_XADES,
    )
    signing_time = etree.SubElement(
        ssp, '{%s}SigningTime' % NS_XADES,
    )
    # AUD-DIAN-34 (2026-10-04): datetime.now() devuelve la hora naive del
    # servidor (UTC en Odoo.sh) -- con el sufijo "-05:00" pegado sin
    # convertir, SigningTime quedaba declarado ~5h en el futuro respecto
    # al instante real, y la DIAN rechazaba la firma (ZE02) de forma
    # idéntica en cada intento. Se usa hora tz-aware America/Bogota
    # (Colombia no tiene DST, el offset -05:00 es siempre correcto una
    # vez la hora de pared ya está en zona horaria real).
    signing_time.text = datetime.now(
        _pytz_timezone('America/Bogota')
    ).strftime('%Y-%m-%dT%H:%M:%S-05:00')

    # SigningCertificate
    # AUD-DIAN-34 (2026-10-04, DC25): el Anexo Tecnico exige al menos 3
    # grupos Cert distintos (hoja + CA intermedia + CA raiz), confirmado
    # tambien por el XPath de la seccion 7.14 Regla-4 que indexa
    # Cert[3]. Antes solo se generaba 1 Cert (la hoja) -- se reemplaza
    # por un Cert completo (CertDigest + IssuerSerial) por cada
    # certificado de la cadena, mismo patron que account_edi_xml_ubl_dian.py
    # (Facturacion Electronica nativa, en produccion) con
    # company.l10n_co_dian_certificate_ids.
    signing_cert = etree.SubElement(
        ssp, '{%s}SigningCertificate' % NS_XADES,
    )
    for chain_cert in chain:
        chain_cert_der = chain_cert.public_bytes(serialization.Encoding.DER)
        cert_elem = etree.SubElement(
            signing_cert, '{%s}Cert' % NS_XADES,
        )
        cert_digest_elem = etree.SubElement(
            cert_elem, '{%s}CertDigest' % NS_XADES,
        )
        etree.SubElement(
            cert_digest_elem, '{%s}DigestMethod' % NS_DS,
            Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
        )
        cert_dv = etree.SubElement(
            cert_digest_elem, '{%s}DigestValue' % NS_DS,
        )
        cert_dv.text = _compute_digest(chain_cert_der)

        issuer_serial = etree.SubElement(
            cert_elem, '{%s}IssuerSerial' % NS_XADES,
        )
        x509_issuer = etree.SubElement(
            issuer_serial, '{%s}X509IssuerName' % NS_DS,
        )
        x509_issuer.text = chain_cert.issuer.rfc4514_string()
        x509_serial = etree.SubElement(
            issuer_serial, '{%s}X509SerialNumber' % NS_DS,
        )
        x509_serial.text = str(chain_cert.serial_number)

    # SignaturePolicyIdentifier
    spi = etree.SubElement(
        ssp, '{%s}SignaturePolicyIdentifier' % NS_XADES,
    )
    sp_elem = etree.SubElement(
        spi, '{%s}SignaturePolicyId' % NS_XADES,
    )
    sp_id_elem = etree.SubElement(
        sp_elem, '{%s}SigPolicyId' % NS_XADES,
    )
    sp_identifier = etree.SubElement(
        sp_id_elem, '{%s}Identifier' % NS_XADES,
    )
    sp_identifier.text = SIGNATURE_POLICY_URL
    # AUD-DIAN-34 (2026-09-14): xades:Description es opcional segun el
    # esquema XAdES (minOccurs=0), pero la implementacion nativa de
    # Facturacion Electronica (l10n_co_dian, en produccion) SIEMPRE lo
    # incluye -- agregado aqui por paralelismo estructural con esa
    # implementacion que si funciona (no por una regla DC0x numerada:
    # el Anexo Tecnico no valida este campo por codigo propio). El texto
    # SI es normativo: la seccion 7.10 del Anexo Tecnico de Nomina
    # especifica literalmente "Política de firma para nóminas
    # electrónicas de la República de Colombia." -- corregido 2026-10-04
    # (Tech Lead detecto que se habia copiado el texto de Facturacion
    # sin cambiar "facturas" por "nóminas").
    sp_description = etree.SubElement(
        sp_id_elem, '{%s}Description' % NS_XADES,
    )
    sp_description.text = (
        'Política de firma para nóminas electrónicas de la '
        'República de Colombia.'
    )

    sp_hash = etree.SubElement(
        sp_elem, '{%s}SigPolicyHash' % NS_XADES,
    )
    etree.SubElement(
        sp_hash, '{%s}DigestMethod' % NS_DS,
        Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
    )
    sp_hash_dv = etree.SubElement(
        sp_hash, '{%s}DigestValue' % NS_DS,
    )
    sp_hash_dv.text = SIGNATURE_POLICY_DIGEST

    # SignerRole
    signer_role = etree.SubElement(
        ssp, '{%s}SignerRole' % NS_XADES,
    )
    claimed = etree.SubElement(
        signer_role, '{%s}ClaimedRoles' % NS_XADES,
    )
    role = etree.SubElement(
        claimed, '{%s}ClaimedRole' % NS_XADES,
    )
    role.text = 'supplier'

    # ===== Calcular digests para KeyInfo y SignedProperties =====
    ki_c14n = etree.tostring(key_info, method='c14n')
    ki_digest = _compute_digest(ki_c14n)

    sp_c14n = etree.tostring(signed_props, method='c14n')
    sp_digest = _compute_digest(sp_c14n)

    # Insertar digests en las references
    dv_ki = etree.SubElement(ref_ki, '{%s}DigestValue' % NS_DS)
    dv_ki.text = ki_digest

    dv_sp = etree.SubElement(ref_sp, '{%s}DigestValue' % NS_DS)
    dv_sp.text = sp_digest

    # ===== Firmar SignedInfo =====
    si_c14n = etree.tostring(signed_info, method='c14n')
    signature_value = _sign_data(private_key, si_c14n)
    sig_value.text = signature_value

    return etree.tostring(
        root, xml_declaration=True, encoding='UTF-8',
        pretty_print=True,
    )
