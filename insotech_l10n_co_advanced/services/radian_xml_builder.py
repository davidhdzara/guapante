# -*- coding: utf-8 -*-
"""RADIAN ApplicationResponse XML Builder.

Generates the UBL 2.1 XML for Events 030, 032, 033, 034, 035.

PURE PYTHON — No Odoo dependencies.
All data is received via dicts, making this portable across Odoo versions.

Callers (radian_event.py) must construct the context dict from Odoo records.
"""

import hashlib
from datetime import datetime


# -------------------------------------------------------------------------
# Hashing helpers
# -------------------------------------------------------------------------

def compute_radian_cude(
        num_de, fec_emi, hor_emi, nit_fe, doc_adq,
        response_code, doc_ref_id, doc_type_code,
        software_pin):
    """Calcula el CUDE de un ApplicationResponse RADIAN.

    Fuente: Anexo Técnico FE v1.9, Sección 11.5 (p670-672)
    """
    cude_string = (
        f"{num_de}{fec_emi}{hor_emi}{nit_fe}{doc_adq}"
        f"{response_code}{doc_ref_id}{doc_type_code}"
        f"{software_pin}"
    )
    return hashlib.sha384(
        cude_string.encode('utf-8')
    ).hexdigest()


def compute_software_security_code(software_id, pin, doc_id):
    """Calcula el SoftwareSecurityCode para ApplicationResponse.

    Formula: SHA384(SoftwareID + PIN + ID)
    """
    raw = f"{software_id}{pin}{doc_id}"
    return hashlib.sha384(raw.encode('utf-8')).hexdigest()


# -------------------------------------------------------------------------
# Claim descriptions
# -------------------------------------------------------------------------

def _get_claim_description(code):
    if code == '01': return 'Documento con inconsistencias'
    if code == '02': return 'Mercancía no entregada totalmente'
    if code == '03': return 'Mercancía no entregada parcialmente'
    if code == '04': return 'Servicio no prestado'
    return 'Reclamo'


# -------------------------------------------------------------------------
# Main XML generator — PURE FUNCTION (receives dicts, not records)
# -------------------------------------------------------------------------

def generate_application_response(ctx):
    """Genera el XML UBL 2.1 para un evento RADIAN.

    Args:
        ctx (dict): Contexto con todos los datos necesarios:
            - event_id (int): ID del evento
            - event_code (str): '030', '032', '033', '034', '035'
            - event_date (datetime): Fecha/hora del evento
            - claim_code (str|None): Código de reclamo (solo para 034)
            - seller_nit (str): NIT limpio del vendedor (OFE)
            - seller_name (str): Nombre del vendedor
            - seller_doc_type (str): Código tipo doc vendedor ('31', '13', etc.)
            - seller_dv (str): Dígito de verificación del vendedor
            - buyer_nit (str): NIT limpio del comprador (ADQ)
            - buyer_name (str): Nombre del comprador
            - buyer_doc_type (str): Código tipo doc comprador
            - buyer_dv (str): Dígito de verificación del comprador
            - software_id (str): DIAN Software ID
            - software_pin (str): DIAN Software PIN
            - cufe (str): CUFE de la factura referenciada
            - invoice_number (str): Número de la factura
            - test_mode (bool): True = habilitación, False = producción

    Returns:
        str: XML string sin firmar
    """
    # Prefix mapping
    prefixes = {
        '030': 'ACR', '032': 'RMD', '033': 'AEX',
        '034': 'RCL', '031': 'REJ', '035': 'ATC',
    }
    descriptions = {
        '030': 'Acuse de recibo de Factura Electrónica de Venta',
        '032': 'Recibo de bien y/o prestación del servicio',
        '033': 'Aceptación expresa de la factura electrónica de venta',
        '034': 'Reclamo de la Factura Electrónica de Venta',
        '031': 'Rechazo de la factura electrónica de venta',
        '035': 'Aceptación Tácita de la factura electrónica de venta',
    }

    event_code = ctx['event_code']
    prefix = prefixes.get(event_code, 'RAD')
    event_num = str(ctx['event_id']).zfill(6)
    ar_id = f"{prefix}{event_num}"

    event_dt = ctx['event_date']
    fec_ar = event_dt.strftime('%Y-%m-%d')
    hor_ar = event_dt.strftime('%H:%M:%S-05:00')

    # NIT handling — caller provides already-cleaned values
    nit_ofe = ctx['seller_nit']
    nit_adq = ctx['buyer_nit']

    dv_ofe = ctx.get('seller_dv', '')
    dv_adq = ctx.get('buyer_dv', '')

    type_ofe = ctx.get('seller_doc_type', '31')
    type_adq = ctx.get('buyer_doc_type', '13')

    # DV attributes — schemeID is 1..1 (mandatory) per Anexo v1.9
    attr_dv_ofe = (
        f'schemeID="{dv_ofe}"' if type_ofe == '31'
        else 'schemeID=""'
    )
    attr_dv_adq = (
        f'schemeID="{dv_adq}"' if type_adq == '31'
        else 'schemeID=""'
    )

    software_pin = ctx.get('software_pin', '')
    software_id = ctx.get('software_id', '')
    cufe_padre = ctx.get('cufe', '')
    invoice_number = ctx.get('invoice_number', '')

    # CUDE calculation
    cude = compute_radian_cude(
        num_de=ar_id,
        fec_emi=fec_ar,
        hor_emi=hor_ar,
        nit_fe=nit_ofe,
        doc_adq=nit_adq,
        response_code=event_code,
        doc_ref_id=invoice_number,
        doc_type_code='01',
        software_pin=software_pin,
    )

    # SoftwareSecurityCode
    software_security_code = compute_software_security_code(
        software_id=software_id,
        pin=software_pin,
        doc_id=ar_id,
    )

    profile_id = (
        'DIAN 2.1: ApplicationResponse de '
        'la Factura Electrónica de Venta'
    )
    customization_id = '1'
    response_code = event_code
    response_desc = descriptions.get(event_code, '')
    profile_execution_id = '2' if ctx.get('test_mode') else '1'

    # SenderParty = Seller (OFE), ReceiverParty = Buyer (ADQ)
    sender_nit = nit_ofe
    sender_dv = dv_ofe
    sender_name = ctx['seller_name']
    sender_type = type_ofe
    sender_attr_dv = attr_dv_ofe
    receiver_nit = nit_adq
    receiver_dv = dv_adq
    receiver_name = ctx['buyer_name']
    receiver_type = type_adq
    receiver_attr_dv = attr_dv_adq

    # LineResponse
    line_response_code = response_code
    line_response_desc = response_desc
    if event_code == '034' and ctx.get('claim_code'):
        line_response_code = ctx['claim_code']
        line_response_desc = _get_claim_description(ctx['claim_code'])

    xml_template = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<ApplicationResponse xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
        xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
        xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
        xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
        xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
        xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1"
        xmlns:xades="http://uri.etsi.org/01903/v1.3.2#"
        xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2 http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-ApplicationResponse-2.1.xsd">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
                <sts:DianExtensions>
                    <sts:InvoiceSource>
                        <cbc:IdentificationCode listAgencyID="6" listAgencyName="United Nations Economic Commission for Europe" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1">CO</cbc:IdentificationCode>
                    </sts:InvoiceSource>
                    <sts:SoftwareProvider>
                        <sts:ProviderID {attr_dv_ofe} schemeName="31" schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">{nit_ofe}</sts:ProviderID>
                        <sts:SoftwareID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">{software_id}</sts:SoftwareID>
                    </sts:SoftwareProvider>
                    <sts:SoftwareSecurityCode schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">{software_security_code}</sts:SoftwareSecurityCode>
                    <sts:AuthorizationProvider>
                        <sts:AuthorizationProviderID schemeID="4" schemeName="31" schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)">800197268</sts:AuthorizationProviderID>
                    </sts:AuthorizationProvider>
                    <sts:QRCode>https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={cufe_padre}</sts:QRCode>
                </sts:DianExtensions>
            </ext:ExtensionContent>
        </ext:UBLExtension>
        <ext:UBLExtension>
            <ext:ExtensionContent>
<!-- ds:Signature -->
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>{customization_id}</cbc:CustomizationID>
    <cbc:ProfileID>{profile_id}</cbc:ProfileID>
    <cbc:ProfileExecutionID>{profile_execution_id}</cbc:ProfileExecutionID>
    <cbc:ID>{ar_id}</cbc:ID>
    <cbc:UUID schemeID="{profile_execution_id}" schemeName="CUDE-SHA384">{cude}</cbc:UUID>
    <cbc:IssueDate>{fec_ar}</cbc:IssueDate>
    <cbc:IssueTime>{hor_ar}</cbc:IssueTime>
    <cbc:Note>{ar_id}{fec_ar}{hor_ar}{nit_ofe}{nit_adq}{response_code}{invoice_number}01{software_pin}</cbc:Note>
    <cac:SenderParty>
        <cac:PartyTaxScheme>
            <cbc:RegistrationName>{sender_name}</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" {sender_attr_dv} schemeName="{sender_type}" schemeVersionID="1">{sender_nit}</cbc:CompanyID>
            <cac:TaxScheme>                                      
                <cbc:ID>01</cbc:ID>
                <cbc:Name>IVA</cbc:Name>
            </cac:TaxScheme>
        </cac:PartyTaxScheme>
    </cac:SenderParty>
    <cac:ReceiverParty>
        <cac:PartyTaxScheme>
            <cbc:RegistrationName>{receiver_name}</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)" {receiver_attr_dv} schemeName="{receiver_type}" schemeVersionID="1">{receiver_nit}</cbc:CompanyID>
            <cac:TaxScheme>
                <cbc:ID>01</cbc:ID>
                <cbc:Name>IVA</cbc:Name>
            </cac:TaxScheme>
        </cac:PartyTaxScheme>
    </cac:ReceiverParty>
    <cac:DocumentResponse>
        <cac:Response>
            <cbc:ResponseCode>{response_code}</cbc:ResponseCode>
            <cbc:Description>{response_desc}</cbc:Description>
        </cac:Response>
        <cac:DocumentReference>
            <cbc:ID>{invoice_number}</cbc:ID>
            <cbc:UUID schemeName="CUFE-SHA384">{cufe_padre}</cbc:UUID>
            <cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>
        </cac:DocumentReference>
        <cac:IssuerParty>
            <cac:Person>
                <cbc:ID {attr_dv_ofe} schemeName="{type_ofe}">{nit_ofe}</cbc:ID>
                <cbc:FirstName>{sender_name}</cbc:FirstName>
                <cbc:FamilyName>Representante</cbc:FamilyName>
                <cbc:JobTitle>Representante Legal</cbc:JobTitle>
                <cbc:OrganizationDepartment>Ventas</cbc:OrganizationDepartment>
            </cac:Person>
        </cac:IssuerParty>
        <cac:LineResponse>
            <cac:LineReference>
                <cbc:LineID>1</cbc:LineID>
            </cac:LineReference>
            <cac:Response>
                <cbc:ResponseCode>{line_response_code}</cbc:ResponseCode>
                <cbc:Description>{line_response_desc}</cbc:Description>
            </cac:Response>
        </cac:LineResponse>
    </cac:DocumentResponse>
</ApplicationResponse>
"""
    return xml_template
