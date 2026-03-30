"""Utilidades DIAN Colombia — Fuente única de verdad.

Funciones puras (sin dependencias de Odoo) para cálculos y
transformaciones requeridas por la DIAN colombiana.

Módulos que usan estas funciones:
- insotech_dian_wizard/services/ubl_generator.py
- insotech_dian_wizard/services/test_data.py
- insotech_l10n_co_advanced/services/radian_xml_builder.py
- insotech_l10n_co_advanced/models/res_partner.py
"""

import re


# =====================================================================
# Dígito de Verificación (DV) — Resolución DIAN
# =====================================================================

def compute_dv(nit_str):
    """Calcula dígito de verificación DIAN para un NIT colombiano.

    Algoritmo oficial de la DIAN basado en factores primos.

    Args:
        nit_str: NIT como string (solo dígitos, sin DV)

    Returns:
        str: Dígito de verificación ('0' a '9')
    """
    factors = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    nit_str = str(nit_str).zfill(15)
    total = 0
    for i, digit in enumerate(reversed(nit_str)):
        total += int(digit) * factors[i]
    remainder = total % 11
    return str(11 - remainder) if remainder >= 2 else str(remainder)


# =====================================================================
# Limpieza de NIT
# =====================================================================

def clean_nit(vat_str, strip_dv=True):
    """Extrae solo dígitos del NIT, opcionalmente sin DV.

    La DIAN espera el NIT sin DV en la mayoría de campos XML.
    Odoo almacena el VAT como NIT+DV concatenados (ej: '9017972495').

    Args:
        vat_str: VAT como viene de Odoo (puede tener guiones, DV, etc.)
        strip_dv: Si True y tiene 10 dígitos, quita el último (DV)

    Returns:
        str: NIT limpio (solo dígitos, sin DV)
    """
    if not vat_str:
        return ''
    digits = re.sub(r'[^0-9]', '', str(vat_str))
    # Odoo stores NIT+DV as 10 digits — strip DV
    if strip_dv and len(digits) == 10:
        digits = digits[:9]
    return digits


# =====================================================================
# Tipo de Documento DIAN
# =====================================================================

# Mapeo de códigos Odoo l10n_co → códigos numéricos DIAN
DOC_TYPE_MAP = {
    'rut': '31',                    # NIT
    'id_card': '13',                # Cédula de Ciudadanía
    'national_citizen_id': '13',    # Cédula de Ciudadanía (Odoo 19)
    'id_document': '13',            # Cédula genérica
    'passport': '41',               # Pasaporte
    'foreign_id_card': '22',        # Cédula de Extranjería
    'foreign_id': '22',             # Alias
    'external_id': '42',            # Documento de identificación extranjero
    'civil_registration': '11',     # Registro Civil
    'niup': '91',                   # NUIP
}


def get_doc_type_code(l10n_co_document_code):
    """Convierte un código de documento Odoo al código numérico DIAN.

    Args:
        l10n_co_document_code: Código de tipo de documento de Odoo
                               (ej: 'rut', 'national_citizen_id')

    Returns:
        str: Código numérico DIAN (ej: '31', '13')
    """
    if not l10n_co_document_code:
        return '13'  # Default: Cédula
    code = str(l10n_co_document_code).lower().strip()
    return DOC_TYPE_MAP.get(code, code)


def get_partner_doc_type(partner):
    """Obtiene el código DIAN del tipo de documento de un res.partner.

    Compatible con Odoo 18 y 19.

    Args:
        partner: res.partner record (Odoo)

    Returns:
        str: Código numérico DIAN ('31', '13', etc.)
    """
    idt = getattr(partner, 'l10n_latam_identification_type_id', None)
    if idt:
        doc_code = getattr(idt, 'l10n_co_document_code', None)
        if doc_code:
            return get_doc_type_code(doc_code)
    # Fallback: empresa = NIT, persona = Cédula
    return '31' if getattr(partner, 'is_company', False) else '13'


# =====================================================================
# Partner → dict DIAN (para XML)
# =====================================================================

def partner_to_dian_dict(partner):
    """Convierte un res.partner de Odoo al dict para XML DIAN.

    Este dict es compatible con _add_party() del ubl_generator y
    con las funciones de radian_xml_builder.

    Args:
        partner: res.partner record (Odoo)

    Returns:
        dict: Datos formateados para XML DIAN
    """
    nit = clean_nit(partner.vat or '')
    doc_type = get_partner_doc_type(partner)
    dv = compute_dv(nit) if doc_type == '31' else ''

    # Código ciudad DANE
    city_code = ''
    city_name = partner.city or ''
    city_obj = getattr(partner, 'city_id', None)
    if city_obj:
        city_code = getattr(city_obj, 'l10n_co_edi_code', '') or ''
        if city_obj.name:
            city_name = city_obj.name

    # Departamento
    state = partner.state_id
    dept_name = state.name if state else ''
    dept_code = state.code if state else ''

    # Régimen fiscal
    tax_level = 'O-48'  # Default: Responsable de IVA
    obligations = getattr(
        partner, 'l10n_co_edi_obligation_type_ids', None)
    if obligations:
        codes = obligations.mapped('name')
        if codes:
            tax_level = ';'.join(codes)

    return {
        'company_name': partner.name or '',
        'nit': nit,
        'dv': dv,
        'document_type': doc_type,
        'additional_account_id': '1' if partner.is_company else '2',
        'tax_scheme_id': '01',
        'tax_scheme_name': 'IVA',
        'tax_level_code': tax_level,
        'address_line': partner.street or '',
        'city_name': city_name,
        'city_code': city_code,
        'department': dept_name,
        'department_code': dept_code,
        'country_code': (
            partner.country_id.code if partner.country_id else 'CO'
        ),
        'country_name': (
            partner.country_id.name if partner.country_id
            else 'Colombia'
        ),
        'postal_zone': partner.zip or '',
        'phone': partner.phone or '',
        'email': partner.email or '',
        'registration_name': partner.name or '',
    }
