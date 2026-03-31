"""Datos emulados para el set de pruebas DIAN.

Contiene constantes y datos ficticios necesarios para generar los XMLs
UBL 2.1 del set de pruebas, sin requerir ninguna configuración real
en Odoo (ni productos, ni contactos, ni categorías).
"""


from odoo.addons.insotech_core.utils.dian import compute_dv


def _compute_dv(nit_str):
    """Wrapper de compatibilidad — delega a insotech_core.utils.dian."""
    return compute_dv(nit_str)


# =====================================================================
# Constantes del entorno de habilitación DIAN
# =====================================================================

DIAN_HAB_RESOLUTION = '18760000001'
DIAN_HAB_PREFIX = 'SETP'
DIAN_HAB_RANGE_FROM = 990000000
DIAN_HAB_RANGE_TO = 995000000

# Resolución técnica de pruebas (datos fijos de la DIAN)
DIAN_HAB_RESOLUTION_DATE = '2019-01-19'
DIAN_HAB_RESOLUTION_END_DATE = '2030-01-19'

# UBL Version
UBL_VERSION = 'UBL 2.1'
CUSTOMIZATION_ID = '10'  # DIAN Colombia

# =====================================================================
# Tipos de documento DIAN
# =====================================================================

DOC_TYPE_INVOICE = '01'        # Factura electrónica de venta
DOC_TYPE_CREDIT_NOTE = '91'    # Nota crédito electrónica
DOC_TYPE_DEBIT_NOTE = '92'     # Nota débito electrónica

# =====================================================================
# Namespaces UBL 2.1 + DIAN
# =====================================================================

NS = {
    'inv': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'ccts': 'urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
    'xades': 'http://uri.etsi.org/01903/v1.3.2#',
    'xades141': 'http://uri.etsi.org/01903/v1.4.1#',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'cn': 'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2',
    'dn': 'urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2',
}

# =====================================================================
# Datos ficticios del EMISOR (facturador)
# =====================================================================

EMITTER = {
    'company_name': 'INFINITY SOLUTIONS TECHNOLOGY S.A.S',
    'nit': '901797249',
    'dv': _compute_dv('901797249'),  # Cálculo automático
    'document_type': '31',  # 31 = NIT
    'tax_scheme_id': '01',  # IVA
    'tax_scheme_name': 'IVA',
    'tax_level_code': 'O-48',  # Responsable de IVA

    # Dirección — DEBE coincidir con RUT (Anexo v1.9)
    'address_line': 'DG 54 19 20',
    'city_name': 'Bello',
    'city_code': '05088',
    'department': 'Antioquia',
    'department_code': '05',
    'country_code': 'CO',
    'country_name': 'Colombia',
    'postal_zone': '051050',

    # Contacto
    'phone': '3028522498',
    'email': 'facturacion@insotech.it',

    # Registro mercantil
    'registration_name': 'INFINITY SOLUTIONS TECHNOLOGY S.A.S',
}

# =====================================================================
# Datos ficticios del RECEPTOR (adquiriente)
# =====================================================================

RECEIVER = {
    'company_name': 'ADQUIRIENTE DE PRUEBAS DIAN',
    'nit': '800199436',
    'dv': _compute_dv('800199436'),
    'document_type': '31',  # 31 = NIT
    'additional_account_id': '1',  # 1 = Persona jurídica
    'tax_scheme_id': '01',  # IVA
    'tax_scheme_name': 'IVA',
    'tax_level_code': 'O-48',  # Responsable de IVA

    # Dirección (Bogotá — datos de prueba)
    'address_line': 'Cra 7 # 1-1',
    'city_name': 'Bogotá, D.C.',
    'city_code': '11001',
    'department': 'Bogotá',
    'department_code': '11',
    'country_code': 'CO',
    'country_name': 'Colombia',
    'postal_zone': '110111',

    'phone': '6011234567',
    'email': 'pruebas@dian.gov.co',
    'registration_name': 'ADQUIRIENTE DE PRUEBAS DIAN',
}

# =====================================================================
# Item ficticio (producto/servicio de prueba)
# =====================================================================

TEST_LINE_ITEM = {
    'description': 'Servicio de consultoría tecnológica (prueba DIAN)',
    'item_code': 'SRV-TEST-001',
    'quantity': '1.00',
    'unit_code': 'EA',  # Each (unidad)
    'unit_price': '100000.00',  # $100.000 COP
    'line_total': '100000.00',
    'tax_percent': '19.00',  # IVA 19%
    'tax_amount': '19000.00',
    'taxable_amount': '100000.00',
    'total_with_tax': '119000.00',
}

# =====================================================================
# Totales del documento (1 ítem)
# =====================================================================

DOC_TOTALS = {
    'line_extension_amount': '100000.00',  # Subtotal sin IVA
    'tax_exclusive_amount': '100000.00',   # Base gravable
    'tax_inclusive_amount': '119000.00',    # Total con IVA
    'payable_amount': '119000.00',         # Total a pagar
    'tax_amount': '19000.00',              # IVA total
    'currency': 'COP',
}

# =====================================================================
# Medios de pago (DIAN codes)
# =====================================================================

PAYMENT_MEANS = {
    'code': '10',  # Efectivo
    'payment_due_date_days': 0,  # Contado
}

# =====================================================================
# Razones de ajuste para NC/ND
# =====================================================================

CREDIT_NOTE_CORRECTION_REASON = {
    'code': '2',  # Anulación de factura electrónica
    'description': 'Anulación de factura electrónica de prueba',
}

DEBIT_NOTE_CORRECTION_REASON = {
    'code': '1',  # Intereses
    'description': 'Intereses por mora — documento de prueba',
}

# =====================================================================
# SOAP endpoints DIAN
# =====================================================================

DIAN_WSDL_HAB = (
    'https://vpfe-hab.dian.gov.co'
    '/WcfDianCustomerServices.svc?wsdl'
)
DIAN_ENDPOINT_HAB = (
    'https://vpfe-hab.dian.gov.co'
    '/WcfDianCustomerServices.svc'
)

DIAN_WSDL_PROD = (
    'https://vpfe.dian.gov.co'
    '/WcfDianCustomerServices.svc?wsdl'
)
DIAN_ENDPOINT_PROD = (
    'https://vpfe.dian.gov.co'
    '/WcfDianCustomerServices.svc'
)

# SOAP Actions
SOAP_ACTION_SEND_TEST_SET = (
    'http://wcf.dian.colombia/IWcfDianCustomerServices'
    '/SendTestSetAsync'
)
SOAP_ACTION_GET_STATUS = (
    'http://wcf.dian.colombia/IWcfDianCustomerServices'
    '/GetStatusZip'
)
SOAP_ACTION_SEND_BILL = (
    'http://wcf.dian.colombia/IWcfDianCustomerServices'
    '/SendBillSync'
)
