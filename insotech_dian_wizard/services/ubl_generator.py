"""Generador de documentos UBL 2.1 para el set de pruebas DIAN.

Genera XMLs conformes con el Anexo Técnico de la DIAN para:
- Factura electrónica de venta (tipo 01)
- Nota Crédito electrónica (tipo 91)
- Nota Débito electrónica (tipo 92)

Todos los datos son emulados — no depende de ninguna configuración
de Odoo (sin productos, contactos, ni categorías).
"""
import logging

_logger = logging.getLogger(__name__)

# Debug: último CUFE calculado (accesible desde el wizard)
last_cufe_debug = {'raw': '', 'hash': ''}

import hashlib
import uuid
from datetime import datetime, timedelta

from lxml import etree

from . import test_data as td


# =====================================================================
# Helper: res.partner → party dict (for generic wizard)
# =====================================================================
# Canonical implementation lives in insotech_core.utils.dian
# Import here for backward compatibility and convenience

from odoo.addons.insotech_core.utils.dian import (
    compute_dv as _compute_dv_canonical,
    clean_nit as _clean_nit,
    get_doc_type_code,
    get_partner_doc_type as _get_partner_doc_type,
    partner_to_dian_dict as partner_to_party_dict,
)



def _el(parent, tag, text=None, **attribs):
    """Crea un sub-elemento XML con texto y atributos opcionales."""
    elem = etree.SubElement(parent, tag)
    if text is not None:
        elem.text = str(text)
    for k, v in attribs.items():
        elem.set(k, str(v))
    return elem


def _cbc(parent, name, text, **attribs):
    """Shortcut para crear elemento cbc:Name."""
    tag = '{%s}%s' % (td.NS['cbc'], name)
    return _el(parent, tag, text, **attribs)


def _cac(parent, name):
    """Shortcut para crear elemento contenedor cac:Name."""
    tag = '{%s}%s' % (td.NS['cac'], name)
    return _el(parent, tag)


# =====================================================================
# Funciones auxiliares
# =====================================================================

def _compute_cufe(
    invoice_number, issue_date, issue_time,
    line_total, tax_01, tax_04, tax_03,
    total_with_tax, nit_emisor, nit_receptor,
    software_pin, environment_type, technical_key,
):
    """Calcula el CUFE (SHA-384) según Anexo Técnico DIAN.

    CUFE = SHA384(NumFac + FecFac + HorFac + ValFac + CodImp1 + ValImp1
           + CodImp2 + ValImp2 + CodImp3 + ValImp3 + ValTot
           + NitOFE + NumAdq + ClTec + TipoAmbie)
    """
    parts = [
        invoice_number,
        issue_date,
        issue_time,
        line_total,
        '01', tax_01,    # IVA
        '04', tax_04,    # ICA (0 para pruebas)
        '03', tax_03,    # INC (0 para pruebas)
        total_with_tax,
        nit_emisor,
        nit_receptor,
        technical_key,
        environment_type,
    ]
    raw = ''.join(parts)
    _logger.info('CUFE raw input: %s', raw)
    cufe_hash = hashlib.sha384(raw.encode('utf-8')).hexdigest()
    last_cufe_debug['raw'] = raw
    last_cufe_debug['hash'] = cufe_hash
    return cufe_hash, raw


def _compute_cude(
    doc_number, issue_date, issue_time,
    line_total, tax_01, tax_04, tax_03,
    total_with_tax, nit_emisor, nit_receptor,
    software_pin, environment_type,
):
    """Calcula el CUDE (SHA-384) para NC/ND.

    Similar al CUFE pero usa PIN de software en vez de Clave Técnica.
    """
    parts = [
        doc_number,
        issue_date,
        issue_time,
        line_total,
        '01', tax_01,
        '04', tax_04,
        '03', tax_03,
        total_with_tax,
        nit_emisor,
        nit_receptor,
        software_pin,
        environment_type,
    ]
    raw = ''.join(parts)
    return hashlib.sha384(raw.encode('utf-8')).hexdigest()


def _build_software_security_code(software_id, software_pin, doc_number):
    """Calcula el SecurityCode del software.

    SoftwareSecurityCode = SHA384(SoftwareID + PIN + NroDocumento)
    """
    raw = software_id + software_pin + doc_number
    return hashlib.sha384(raw.encode('utf-8')).hexdigest()


# =====================================================================
# Builders de secciones XML
# =====================================================================

def _add_ubl_extensions(root, ns_ext):
    """Agrega UBLExtensions con placeholder para firma y DIAN extensions."""
    extensions = _el(root, '{%s}UBLExtensions' % ns_ext)

    # Extension 1: DIAN authorization info (se llena después)
    ext1 = _el(extensions, '{%s}UBLExtension' % ns_ext)
    ext1_content = _el(ext1, '{%s}ExtensionContent' % ns_ext)

    # Extension 2: Digital signature placeholder
    ext2 = _el(extensions, '{%s}UBLExtension' % ns_ext)
    ext2_content = _el(ext2, '{%s}ExtensionContent' % ns_ext)

    return ext1_content, ext2_content


def _add_dian_extensions(
    parent, software_id, software_pin, doc_number,
    technical_key=None, software_security_code=None,
    cufe_or_cude=None, emitter_data=None,
):
    """Agrega sts:DianExtensions con InvoiceControl y SoftwareProvider."""
    ns_sts = td.NS['sts']
    ns_cbc = td.NS['cbc']

    dian_ext = _el(parent, '{%s}DianExtensions' % ns_sts)

    # InvoiceControl (solo para facturas)
    if technical_key:
        inv_control = _el(dian_ext, '{%s}InvoiceControl' % ns_sts)
        _el(inv_control, '{%s}InvoiceAuthorization' % ns_sts,
            td.DIAN_HAB_RESOLUTION)

        auth_period = _el(inv_control, '{%s}AuthorizationPeriod' % ns_sts)
        _el(auth_period, '{%s}StartDate' % ns_cbc,
            td.DIAN_HAB_RESOLUTION_DATE)
        _el(auth_period, '{%s}EndDate' % ns_cbc,
            td.DIAN_HAB_RESOLUTION_END_DATE)

        auth_range = _el(inv_control, '{%s}AuthorizedInvoices' % ns_sts)
        _el(auth_range, '{%s}Prefix' % ns_sts, td.DIAN_HAB_PREFIX)
        _el(auth_range, '{%s}From' % ns_sts, td.DIAN_HAB_RANGE_FROM)
        _el(auth_range, '{%s}To' % ns_sts, td.DIAN_HAB_RANGE_TO)

    # InvoiceSource
    inv_source = _el(dian_ext, '{%s}InvoiceSource' % ns_sts)
    _el(inv_source, '{%s}IdentificationCode' % ns_cbc, 'CO',
        listAgencyID='6', listAgencyName='United Nations Economic '
        'Commission for Europe', listSchemeURI='urn:oasis:names:'
        'specification:ubl:codelist:gc:CountryIdentificationCode-2.1')

    # SoftwareProvider — reads from emitter_data (dynamic) or
    # td.EMITTER (fallback for backward compat)
    _emitter = emitter_data or td.EMITTER
    sp = _el(dian_ext, '{%s}SoftwareProvider' % ns_sts)
    _el(sp, '{%s}ProviderID' % ns_sts, _emitter['nit'],
        schemeAgencyID='195', schemeAgencyName='CO, DIAN '
        '(Dirección de Impuestos y Aduanas Nacionales)',
        schemeID=_emitter['dv'],
        schemeName='31')
    _el(sp, '{%s}SoftwareID' % ns_sts, software_id,
        schemeAgencyID='195', schemeAgencyName='CO, DIAN '
        '(Dirección de Impuestos y Aduanas Nacionales)')

    # SoftwareSecurityCode
    if not software_security_code:
        software_security_code = _build_software_security_code(
            software_id, software_pin, doc_number,
        )
    _el(dian_ext, '{%s}SoftwareSecurityCode' % ns_sts,
        software_security_code, schemeAgencyID='195',
        schemeAgencyName='CO, DIAN '
        '(Dirección de Impuestos y Aduanas Nacionales)')

    # AuthorizationProvider (FAB31 — NIT de la DIAN)
    auth_prov = _el(dian_ext, '{%s}AuthorizationProvider' % ns_sts)
    _el(auth_prov, '{%s}AuthorizationProviderID' % ns_sts,
        '800197268',  # NIT de la DIAN
        schemeAgencyID='195',
        schemeAgencyName='CO, DIAN '
        '(Dirección de Impuestos y Aduanas Nacionales)',
        schemeID='4', schemeName='31')

    # QR Code (FAB36)
    if cufe_or_cude:
        qr_url = (
            'https://catalogo-vpfe-hab.dian.gov.co'
            '/document/searchqr?documentkey=%s'
            % cufe_or_cude
        )
        _el(dian_ext, '{%s}QRCode' % ns_sts, qr_url)

    return dian_ext


def _add_party(parent, party_data, role_tag='AccountingSupplierParty'):
    """Agrega un bloque cac:AccountingSupplierParty o Customer."""
    ns_cac = td.NS['cac']
    ns_cbc = td.NS['cbc']

    supplier = _el(parent, '{%s}%s' % (ns_cac, role_tag))
    _cbc(supplier, 'AdditionalAccountID',
         party_data.get('additional_account_id', '1'))

    party = _cac(supplier, 'Party')

    # PartyName
    party_name = _cac(party, 'PartyName')
    _cbc(party_name, 'Name', party_data['company_name'])

    # PhysicalLocation
    phys_loc = _cac(party, 'PhysicalLocation')
    address = _cac(phys_loc, 'Address')
    _cbc(address, 'ID', party_data['city_code'])
    _cbc(address, 'CityName', party_data['city_name'])
    _cbc(address, 'PostalZone', party_data['postal_zone'])
    _cbc(address, 'CountrySubentity', party_data['department'])
    _cbc(address, 'CountrySubentityCode', party_data['department_code'])
    addr_line = _cac(address, 'AddressLine')
    _cbc(addr_line, 'Line', party_data['address_line'])
    country = _cac(address, 'Country')
    _cbc(country, 'IdentificationCode', party_data['country_code'])
    _cbc(country, 'Name', party_data['country_name'],
         languageID='es')

    # PartyTaxScheme
    pts = _cac(party, 'PartyTaxScheme')
    _cbc(pts, 'RegistrationName', party_data['registration_name'])
    _cbc(pts, 'CompanyID', party_data['nit'],
         schemeAgencyID='195',
         schemeAgencyName='CO, DIAN (Dirección de Impuestos y '
         'Aduanas Nacionales)',
         schemeID=party_data['dv'],
         schemeName=party_data['document_type'])
    _cbc(pts, 'TaxLevelCode', party_data['tax_level_code'],
         listName='48')
    reg_addr = _cac(pts, 'RegistrationAddress')
    _cbc(reg_addr, 'ID', party_data['city_code'])
    _cbc(reg_addr, 'CityName', party_data['city_name'])
    _cbc(reg_addr, 'PostalZone', party_data['postal_zone'])
    _cbc(reg_addr, 'CountrySubentity', party_data['department'])
    _cbc(reg_addr, 'CountrySubentityCode',
         party_data['department_code'])
    reg_addr_line = _cac(reg_addr, 'AddressLine')
    _cbc(reg_addr_line, 'Line', party_data['address_line'])
    reg_country = _cac(reg_addr, 'Country')
    _cbc(reg_country, 'IdentificationCode',
         party_data['country_code'])
    _cbc(reg_country, 'Name', party_data['country_name'],
         languageID='es')

    tax_scheme = _cac(pts, 'TaxScheme')
    _cbc(tax_scheme, 'ID', party_data['tax_scheme_id'])
    _cbc(tax_scheme, 'Name', party_data['tax_scheme_name'])

    # PartyLegalEntity
    ple = _cac(party, 'PartyLegalEntity')
    _cbc(ple, 'RegistrationName', party_data['registration_name'])
    _cbc(ple, 'CompanyID', party_data['nit'],
         schemeAgencyID='195',
         schemeAgencyName='CO, DIAN (Direcci\u00f3n de Impuestos y '
         'Aduanas Nacionales)',
         schemeID=party_data['dv'],
         schemeName=party_data['document_type'])
    # CorporateRegistrationScheme (FAB10a — prefijo + sucursal)
    crs = _cac(ple, 'CorporateRegistrationScheme')
    if role_tag == 'AccountingSupplierParty':
        _cbc(crs, 'ID', td.DIAN_HAB_PREFIX)
    _cbc(crs, 'Name', party_data.get('branch_code', '0'))

    # Contact
    contact = _cac(party, 'Contact')
    _cbc(contact, 'Telephone', party_data['phone'])
    _cbc(contact, 'ElectronicMail', party_data['email'])

    return supplier


def _add_tax_total(parent):
    """Agrega cac:TaxTotal con IVA 19%."""
    ns_cac = td.NS['cac']
    ns_cbc = td.NS['cbc']
    item = td.TEST_LINE_ITEM
    totals = td.DOC_TOTALS

    tax_total = _cac(parent, 'TaxTotal')
    _cbc(tax_total, 'TaxAmount', totals['tax_amount'],
         currencyID=totals['currency'])

    subtotal = _cac(tax_total, 'TaxSubtotal')
    _cbc(subtotal, 'TaxableAmount', item['taxable_amount'],
         currencyID=totals['currency'])
    _cbc(subtotal, 'TaxAmount', item['tax_amount'],
         currencyID=totals['currency'])

    tax_cat = _cac(subtotal, 'TaxCategory')
    _cbc(tax_cat, 'Percent', item['tax_percent'])
    scheme = _cac(tax_cat, 'TaxScheme')
    _cbc(scheme, 'ID', '01')
    _cbc(scheme, 'Name', 'IVA')

    return tax_total


def _add_monetary_total(parent, tag_name='LegalMonetaryTotal'):
    """Agrega cac:LegalMonetaryTotal."""
    ns_cac = td.NS['cac']
    ns_cbc = td.NS['cbc']
    t = td.DOC_TOTALS

    lmt = _cac(parent, tag_name)
    _cbc(lmt, 'LineExtensionAmount', t['line_extension_amount'],
         currencyID=t['currency'])
    _cbc(lmt, 'TaxExclusiveAmount', t['tax_exclusive_amount'],
         currencyID=t['currency'])
    _cbc(lmt, 'TaxInclusiveAmount', t['tax_inclusive_amount'],
         currencyID=t['currency'])
    _cbc(lmt, 'PayableAmount', t['payable_amount'],
         currencyID=t['currency'])

    return lmt


def _add_invoice_line(parent, line_number=1):
    """Agrega una línea de factura con datos de prueba."""
    ns_cac = td.NS['cac']
    ns_cbc = td.NS['cbc']
    item = td.TEST_LINE_ITEM
    t = td.DOC_TOTALS

    line = _cac(parent, 'InvoiceLine')
    _cbc(line, 'ID', str(line_number))
    _cbc(line, 'InvoicedQuantity', item['quantity'],
         unitCode=item['unit_code'])
    _cbc(line, 'LineExtensionAmount', item['line_total'],
         currencyID=t['currency'])

    # AllowanceCharge (sin descuento — Regla FBE01)
    ac = _cac(line, 'AllowanceCharge')
    _cbc(ac, 'ChargeIndicator', 'false')
    _cbc(ac, 'MultiplierFactorNumeric', '0.00')
    _cbc(ac, 'Amount', '0.00', currencyID=t['currency'])
    _cbc(ac, 'BaseAmount', item['line_total'],
         currencyID=t['currency'])

    # TaxTotal en línea
    _add_tax_total(line)

    # Item
    inv_item = _cac(line, 'Item')
    _cbc(inv_item, 'Description', item['description'])

    # StandardItemIdentification
    sid = _cac(inv_item, 'StandardItemIdentification')
    _cbc(sid, 'ID', item['item_code'], schemeID='999',
         schemeName='Estándar de adopción del contribuyente',
         schemeAgencyID='195')

    # Price
    price = _cac(line, 'Price')
    _cbc(price, 'PriceAmount', item['unit_price'],
         currencyID=t['currency'])
    _cbc(price, 'BaseQuantity', '1.00', unitCode=item['unit_code'])

    return line


def _add_credit_note_line(parent, line_number=1):
    """Agrega una línea de nota crédito con datos de prueba."""
    ns_cac = td.NS['cac']
    ns_cbc = td.NS['cbc']
    item = td.TEST_LINE_ITEM
    t = td.DOC_TOTALS

    line = _cac(parent, 'CreditNoteLine')
    _cbc(line, 'ID', str(line_number))
    _cbc(line, 'CreditedQuantity', item['quantity'],
         unitCode=item['unit_code'])
    _cbc(line, 'LineExtensionAmount', item['line_total'],
         currencyID=t['currency'])

    # AllowanceCharge (sin descuento — Regla FBE01)
    ac = _cac(line, 'AllowanceCharge')
    _cbc(ac, 'ChargeIndicator', 'false')
    _cbc(ac, 'MultiplierFactorNumeric', '0.00')
    _cbc(ac, 'Amount', '0.00', currencyID=t['currency'])
    _cbc(ac, 'BaseAmount', item['line_total'],
         currencyID=t['currency'])

    _add_tax_total(line)

    inv_item = _cac(line, 'Item')
    _cbc(inv_item, 'Description', item['description'])
    sid = _cac(inv_item, 'StandardItemIdentification')
    _cbc(sid, 'ID', item['item_code'], schemeID='999',
         schemeName='Estándar de adopción del contribuyente',
         schemeAgencyID='195')

    price = _cac(line, 'Price')
    _cbc(price, 'PriceAmount', item['unit_price'],
         currencyID=t['currency'])
    _cbc(price, 'BaseQuantity', '1.00', unitCode=item['unit_code'])

    return line


def _add_debit_note_line(parent, line_number=1):
    """Agrega una línea de nota débito con datos de prueba."""
    ns_cac = td.NS['cac']
    ns_cbc = td.NS['cbc']
    item = td.TEST_LINE_ITEM
    t = td.DOC_TOTALS

    line = _cac(parent, 'DebitNoteLine')
    _cbc(line, 'ID', str(line_number))
    _cbc(line, 'DebitedQuantity', item['quantity'],
         unitCode=item['unit_code'])
    _cbc(line, 'LineExtensionAmount', item['line_total'],
         currencyID=t['currency'])

    # AllowanceCharge (sin descuento — Regla FBE01)
    ac = _cac(line, 'AllowanceCharge')
    _cbc(ac, 'ChargeIndicator', 'false')
    _cbc(ac, 'MultiplierFactorNumeric', '0.00')
    _cbc(ac, 'Amount', '0.00', currencyID=t['currency'])
    _cbc(ac, 'BaseAmount', item['line_total'],
         currencyID=t['currency'])

    _add_tax_total(line)

    inv_item = _cac(line, 'Item')
    _cbc(inv_item, 'Description', item['description'])
    sid = _cac(inv_item, 'StandardItemIdentification')
    _cbc(sid, 'ID', item['item_code'], schemeID='999',
         schemeName='Estándar de adopción del contribuyente',
         schemeAgencyID='195')

    price = _cac(line, 'Price')
    _cbc(price, 'PriceAmount', item['unit_price'],
         currencyID=t['currency'])
    _cbc(price, 'BaseQuantity', '1.00', unitCode=item['unit_code'])

    return line


# =====================================================================
# Generadores principales
# =====================================================================

def generate_invoice(
    number, software_id, software_pin, technical_key,
    issue_date=None, issue_time=None, environment_type='2',
    emitter_data=None,
):
    """Genera un XML UBL 2.1 de factura electrónica de prueba.

    Args:
        number: Número consecutivo (ej. 990000001)
        software_id: Software ID de la DIAN
        software_pin: Software PIN de la DIAN
        technical_key: Clave técnica del set de pruebas
        issue_date: Fecha de emisión (default: hoy)
        issue_time: Hora de emisión (default: ahora)
        environment_type: '1'=Producción, '2'=Pruebas

    Returns:
        bytes: XML como bytes UTF-8
    """
    ns_inv = td.NS['inv']
    ns_cbc = td.NS['cbc']
    ns_cac = td.NS['cac']
    ns_ext = td.NS['ext']

    now = datetime.now()
    if not issue_date:
        issue_date = now.strftime('%Y-%m-%d')
    if not issue_time:
        issue_time = now.strftime('%H:%M:%S-05:00')

    doc_number = '%s%s' % (td.DIAN_HAB_PREFIX, number)
    t = td.DOC_TOTALS

    # Root element
    nsmap = {
        None: ns_inv,
        'cac': ns_cac,
        'cbc': ns_cbc,
        'ext': ns_ext,
        'sts': td.NS['sts'],
        'ds': td.NS['ds'],
        'xades': td.NS['xades'],
        'xades141': td.NS['xades141'],
        'xsi': td.NS['xsi'],
    }
    root = etree.Element('{%s}Invoice' % ns_inv, nsmap=nsmap)

    # UBLExtensions (DIAN + Signature placeholder)
    ext1_content, ext2_content = _add_ubl_extensions(root, ns_ext)

    emitter = emitter_data or td.EMITTER

    # Compute CUFE FIRST (needed for QR Code in DianExtensions)
    cufe, cufe_raw = _compute_cufe(
        doc_number, issue_date, issue_time,
        t['line_extension_amount'], t['tax_amount'], '0.00', '0.00',
        t['tax_inclusive_amount'], emitter['nit'],
        td.RECEIVER['nit'], software_pin,
        environment_type, technical_key,
    )

    _add_dian_extensions(
        ext1_content, software_id, software_pin,
        doc_number, technical_key=technical_key,
        cufe_or_cude=cufe, emitter_data=emitter,
    )

    # UBL header
    _cbc(root, 'UBLVersionID', td.UBL_VERSION)
    _cbc(root, 'CustomizationID', td.CUSTOMIZATION_ID)
    _cbc(root, 'ProfileID',
         'DIAN 2.1: Factura Electr\u00f3nica de Venta')
    _cbc(root, 'ProfileExecutionID', environment_type)

    _cbc(root, 'ID', doc_number)

    # UUID (CUFE)
    _cbc(root, 'UUID', cufe, schemeID=environment_type,
         schemeName='CUFE-SHA384')

    _cbc(root, 'IssueDate', issue_date)
    _cbc(root, 'IssueTime', issue_time)
    _cbc(root, 'InvoiceTypeCode', td.DOC_TYPE_INVOICE)
    # Note con cadena de entrada del CUFE (como en Generica.xml línea 121)
    cufe_raw = ''.join([
        doc_number, issue_date, issue_time,
        t['line_extension_amount'],
        '01', t['tax_amount'], '04', '0.00', '03', '0.00',
        t['tax_inclusive_amount'], emitter['nit'],
        td.RECEIVER['nit'], technical_key, environment_type,
    ])
    _cbc(root, 'Note', cufe_raw)
    _cbc(root, 'DocumentCurrencyCode', t['currency'])
    _cbc(root, 'LineCountNumeric', '1')

    # Parties
    _add_party(root, emitter, 'AccountingSupplierParty')
    _add_party(root, td.RECEIVER, 'AccountingCustomerParty')

    # Delivery (oficial DIAN: Delivery > DeliveryAddress)
    delivery = _cac(root, 'Delivery')
    del_addr = _cac(delivery, 'DeliveryAddress')
    _cbc(del_addr, 'ID', td.RECEIVER['city_code'])
    _cbc(del_addr, 'CityName', td.RECEIVER['city_name'])
    _cbc(del_addr, 'CountrySubentity', td.RECEIVER['department'])
    _cbc(del_addr, 'CountrySubentityCode',
         td.RECEIVER['department_code'])
    del_addr_line = _cac(del_addr, 'AddressLine')
    _cbc(del_addr_line, 'Line', td.RECEIVER['address_line'])
    del_country = _cac(del_addr, 'Country')
    _cbc(del_country, 'IdentificationCode',
         td.RECEIVER['country_code'])
    _cbc(del_country, 'Name', td.RECEIVER['country_name'],
         languageID='es')

    # PaymentMeans
    pm = _cac(root, 'PaymentMeans')
    _cbc(pm, 'ID', '1')  # Medio de pago
    _cbc(pm, 'PaymentMeansCode', '10')  # 10=Efectivo
    _cbc(pm, 'PaymentDueDate', issue_date)
    _cbc(pm, 'PaymentID', doc_number)

    # TaxTotal
    _add_tax_total(root)

    # LegalMonetaryTotal
    _add_monetary_total(root)

    # InvoiceLine
    _add_invoice_line(root)

    return etree.tostring(
        root, xml_declaration=True, encoding='UTF-8',
        pretty_print=True,
    )


def generate_credit_note(
    number, ref_invoice_number, ref_cufe,
    software_id, software_pin,
    issue_date=None, issue_time=None, environment_type='2',
    emitter_data=None,
):
    """Genera un XML UBL 2.1 de nota crédito electrónica de prueba.

    Args:
        number: Número consecutivo
        ref_invoice_number: Número de la factura referenciada
        ref_cufe: CUFE de la factura referenciada
        software_id: Software ID
        software_pin: Software PIN
        issue_date: Fecha de emisión
        issue_time: Hora de emisión
        environment_type: '1' o '2'

    Returns:
        bytes: XML como bytes UTF-8
    """
    ns_cn = td.NS['cn']
    ns_cbc = td.NS['cbc']
    ns_cac = td.NS['cac']
    ns_ext = td.NS['ext']

    now = datetime.now()
    if not issue_date:
        issue_date = now.strftime('%Y-%m-%d')
    if not issue_time:
        issue_time = now.strftime('%H:%M:%S-05:00')

    doc_number = '%s%s' % (td.DIAN_HAB_PREFIX, number)
    t = td.DOC_TOTALS

    nsmap = {
        None: ns_cn,
        'cac': ns_cac,
        'cbc': ns_cbc,
        'ext': ns_ext,
        'sts': td.NS['sts'],
        'ds': td.NS['ds'],
        'xades': td.NS['xades'],
        'xades141': td.NS['xades141'],
        'xsi': td.NS['xsi'],
    }
    root = etree.Element('{%s}CreditNote' % ns_cn, nsmap=nsmap)

    ext1_content, ext2_content = _add_ubl_extensions(root, ns_ext)

    emitter = emitter_data or td.EMITTER

    # Compute CUDE FIRST (needed for QR Code)
    cude = _compute_cude(
        doc_number, issue_date, issue_time,
        t['line_extension_amount'], t['tax_amount'], '0.00', '0.00',
        t['tax_inclusive_amount'], emitter['nit'],
        td.RECEIVER['nit'], software_pin, environment_type,
    )

    _add_dian_extensions(
        ext1_content, software_id, software_pin, doc_number,
        cufe_or_cude=cude, emitter_data=emitter,
    )

    _cbc(root, 'UBLVersionID', td.UBL_VERSION)
    _cbc(root, 'CustomizationID', '20')  # 20 = NC con referencia
    _cbc(root, 'ProfileID', 'DIAN 2.1: Nota Cr\u00e9dito')
    _cbc(root, 'ProfileExecutionID', environment_type)
    _cbc(root, 'ID', doc_number)

    _cbc(root, 'UUID', cude, schemeID=environment_type,
         schemeName='CUDE-SHA384')

    _cbc(root, 'IssueDate', issue_date)
    _cbc(root, 'IssueTime', issue_time)
    _cbc(root, 'CreditNoteTypeCode', td.DOC_TYPE_CREDIT_NOTE)
    _cbc(root, 'Note', 'Nota cr\u00e9dito de prueba \u2014 habilitaci\u00f3n DIAN.')
    _cbc(root, 'DocumentCurrencyCode', t['currency'])
    _cbc(root, 'LineCountNumeric', '1')

    # DiscrepancyResponse (raz\u00f3n de la NC)
    dr = _cac(root, 'DiscrepancyResponse')
    _cbc(dr, 'ReferenceID', ref_invoice_number)
    _cbc(dr, 'ResponseCode',
         td.CREDIT_NOTE_CORRECTION_REASON['code'])
    _cbc(dr, 'Description',
         td.CREDIT_NOTE_CORRECTION_REASON['description'])

    # BillingReference (factura referenciada)
    br = _cac(root, 'BillingReference')
    inv_ref = _cac(br, 'InvoiceDocumentReference')
    _cbc(inv_ref, 'ID', ref_invoice_number)
    _cbc(inv_ref, 'UUID', ref_cufe, schemeName='CUFE-SHA384')
    _cbc(inv_ref, 'IssueDate', issue_date)

    # Parties
    _add_party(root, emitter, 'AccountingSupplierParty')
    _add_party(root, td.RECEIVER, 'AccountingCustomerParty')

    pm = _cac(root, 'PaymentMeans')
    _cbc(pm, 'ID', '1')
    _cbc(pm, 'PaymentMeansCode', '10')

    _add_tax_total(root)
    _add_monetary_total(root, 'LegalMonetaryTotal')
    _add_credit_note_line(root)

    return etree.tostring(
        root, xml_declaration=True, encoding='UTF-8',
        pretty_print=True,
    )


def generate_debit_note(
    number, ref_invoice_number, ref_cufe,
    software_id, software_pin,
    issue_date=None, issue_time=None, environment_type='2',
    emitter_data=None,
):
    """Genera un XML UBL 2.1 de nota débito electrónica de prueba."""
    ns_dn = td.NS['dn']
    ns_cbc = td.NS['cbc']
    ns_cac = td.NS['cac']
    ns_ext = td.NS['ext']

    now = datetime.now()
    if not issue_date:
        issue_date = now.strftime('%Y-%m-%d')
    if not issue_time:
        issue_time = now.strftime('%H:%M:%S-05:00')

    doc_number = '%s%s' % (td.DIAN_HAB_PREFIX, number)
    t = td.DOC_TOTALS

    nsmap = {
        None: ns_dn,
        'cac': ns_cac,
        'cbc': ns_cbc,
        'ext': ns_ext,
        'sts': td.NS['sts'],
        'ds': td.NS['ds'],
        'xades': td.NS['xades'],
        'xades141': td.NS['xades141'],
        'xsi': td.NS['xsi'],
    }
    root = etree.Element('{%s}DebitNote' % ns_dn, nsmap=nsmap)

    ext1_content, ext2_content = _add_ubl_extensions(root, ns_ext)

    emitter = emitter_data or td.EMITTER

    # Compute CUDE FIRST (needed for QR Code)
    cude = _compute_cude(
        doc_number, issue_date, issue_time,
        t['line_extension_amount'], t['tax_amount'], '0.00', '0.00',
        t['tax_inclusive_amount'], emitter['nit'],
        td.RECEIVER['nit'], software_pin, environment_type,
    )

    _add_dian_extensions(
        ext1_content, software_id, software_pin, doc_number,
        cufe_or_cude=cude, emitter_data=emitter,
    )

    _cbc(root, 'UBLVersionID', td.UBL_VERSION)
    _cbc(root, 'CustomizationID', '30')  # 30 = ND con referencia
    _cbc(root, 'ProfileID', 'DIAN 2.1: Nota D\u00e9bito')
    _cbc(root, 'ProfileExecutionID', environment_type)
    _cbc(root, 'ID', doc_number)

    _cbc(root, 'UUID', cude, schemeID=environment_type,
         schemeName='CUDE-SHA384')

    _cbc(root, 'IssueDate', issue_date)
    _cbc(root, 'IssueTime', issue_time)
    _cbc(root, 'Note', 'Nota d\u00e9bito de prueba \u2014 habilitaci\u00f3n DIAN.')
    _cbc(root, 'DocumentCurrencyCode', t['currency'])
    _cbc(root, 'LineCountNumeric', '1')

    # DiscrepancyResponse
    dr = _cac(root, 'DiscrepancyResponse')
    _cbc(dr, 'ReferenceID', ref_invoice_number)
    _cbc(dr, 'ResponseCode',
         td.DEBIT_NOTE_CORRECTION_REASON['code'])
    _cbc(dr, 'Description',
         td.DEBIT_NOTE_CORRECTION_REASON['description'])

    # BillingReference
    br = _cac(root, 'BillingReference')
    inv_ref = _cac(br, 'InvoiceDocumentReference')
    _cbc(inv_ref, 'ID', ref_invoice_number)
    _cbc(inv_ref, 'UUID', ref_cufe, schemeName='CUFE-SHA384')
    _cbc(inv_ref, 'IssueDate', issue_date)

    # Parties
    _add_party(root, emitter, 'AccountingSupplierParty')
    _add_party(root, td.RECEIVER, 'AccountingCustomerParty')

    pm = _cac(root, 'PaymentMeans')
    _cbc(pm, 'ID', '1')
    _cbc(pm, 'PaymentMeansCode', '10')

    _add_tax_total(root)

    # RequestedMonetaryTotal (para ND, no LegalMonetaryTotal)
    _add_monetary_total(root, 'RequestedMonetaryTotal')

    _add_debit_note_line(root)

    return etree.tostring(
        root, xml_declaration=True, encoding='UTF-8',
        pretty_print=True,
    )
