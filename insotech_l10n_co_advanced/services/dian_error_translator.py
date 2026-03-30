# -*- coding: utf-8 -*-
"""DIAN Error Translator — Diagnóstico Inteligente de Errores.

Pure-Python service that translates cryptic DIAN rejection codes
into user-friendly Spanish messages with actionable guidance.

This module has ZERO dependency on Odoo, making it fully testable
with plain ``python3 -m pytest`` or a standalone script.

Usage from Odoo code::

    from ..services.dian_error_translator import (
        sanitize_dian_error,
        translate_dian_error,
    )

    clean = sanitize_dian_error(raw_html_from_dian)
    diagnosis = translate_dian_error(clean)

Legal basis:
- Resolución 000165 de 2023 (Anexo Técnico v1.9)
- Errores validados contra DIAN real (habilitación 2026-03-22)
"""

import html
import re

# ---------------------------------------------------------------------------
# Try importing lxml (available on all Odoo installs).  If somehow
# missing, the sanitizer will fall back to a regex-based cleaner.
# ---------------------------------------------------------------------------
try:
    from lxml import html as lxml_html
    _HAS_LXML = True
except ImportError:
    _HAS_LXML = False


# =========================================================================
# DIAN ERROR MAP — 13 reglas reales de producción
# =========================================================================
# Each entry is a dict with:
#   code     – DIAN rule identifier (for display)
#   patterns – list of regex/substring patterns to match in the error text
#   message  – user-friendly Spanish explanation
#   details  – additional guidance (fields to fix, etc.)
#   category – 'partner' | 'journal' | 'technical'
#   fields   – list of Odoo field paths affected (informational)
# =========================================================================

DIAN_ERROR_MAP = [
    {
        'code': 'FAJ28',
        'patterns': ['FAJ28', 'Delivery', 'DeliveryAddress',
                     'CityName, CountrySubentity'],
        'message': 'Dirección del contacto incompleta para facturación electrónica',
        'details': (
            'La DIAN requiere dirección completa del contacto incluyendo:\n'
            '• Ciudad (con código DANE)\n'
            '• Departamento\n'
            '• Código postal\n'
            '• Dirección (calle/carrera)'
        ),
        'category': 'partner',
        'fields': ['city_id', 'state_id', 'zip', 'street'],
    },
    {
        'code': 'FAK24',
        'patterns': ['FAK24', 'gito de verificaci',
                     'verification digit', 'DigitoVerificacion'],
        'message': 'Dígito de verificación (DV) incorrecto',
        'details': (
            'El DV del NIT no coincide con el cálculo esperado por la DIAN.\n'
            'Verifique que el NIT y DV del contacto estén correctos.\n'
            'El DV se calcula automáticamente a partir del NIT.'
        ),
        'category': 'partner',
        'fields': ['vat', 'l10n_co_verification_digit'],
    },
    {
        'code': 'FAK41',
        'patterns': ['FAK41', 'TaxScheme', 'TaxLevelCode',
                     'gimen tributario', 'código válido'],
        'message': 'Régimen tributario del contacto no es válido',
        'details': (
            'El código de responsabilidad fiscal del contacto no corresponde\n'
            'al catálogo de la DIAN. Configure el campo "Nivel tributario"\n'
            'del contacto con un valor válido (ej: R-99-PN para no responsable).'
        ),
        'category': 'partner',
        'fields': ['l10n_co_tax_level_code_id'],
    },
    {
        'code': 'FAB35',
        'patterns': ['FAB35', 'tipo de documento',
                     'identification type', 'schemeName'],
        'message': 'Tipo de documento de identidad no configurado',
        'details': (
            'El contacto no tiene un tipo de documento de identidad válido.\n'
            'Seleccione CC (Cédula), NIT, CE (Cédula Extranjería), etc.\n'
            'en el campo "Tipo de identificación" del contacto.'
        ),
        'category': 'partner',
        'fields': ['l10n_latam_identification_type_id'],
    },
    {
        'code': 'FAK61',
        'patterns': ['FAK61', 'FirstName', 'FamilyName',
                     'nombre', 'apellido'],
        'message': 'Persona natural sin nombre/apellido separado',
        'details': (
            'Para personas naturales, la DIAN requiere nombre y apellido\n'
            'como campos separados. Verifique que el contacto tenga\n'
            'configurados los campos "Primer nombre" y "Primer apellido".'
        ),
        'category': 'partner',
        'fields': ['firstname', 'lastname'],
    },
    {
        'code': 'FAK28',
        'patterns': ['FAK28', 'RegistrationAddress'],
        'message': 'Dirección de registro del contacto faltante',
        'details': (
            'La DIAN requiere la dirección de registro (RegistrationAddress)\n'
            'del contacto. Verifique que la dirección completa esté\n'
            'configurada en los datos del contacto.'
        ),
        'category': 'partner',
        'fields': ['street', 'city_id', 'state_id'],
    },
    {
        'code': 'FAN02',
        'patterns': ['FAN02', 'PaymentMeans', 'todo de pago',
                     'PaymentMeansCode'],
        'message': 'Método de pago no válido en el diario',
        'details': (
            'El método de pago configurado no es válido para la DIAN.\n'
            'Verifique la configuración del método de pago en el diario\n'
            'de facturación electrónica.'
        ),
        'category': 'journal',
        'fields': ['l10n_co_edi_payment_option_id'],
    },
    {
        'code': 'FAD06',
        'patterns': ['FAD06', 'CUFE', 'CUDE'],
        'message': 'Error en cálculo del CUFE — contactar soporte técnico',
        'details': (
            'El CUFE (Código Único de Factura Electrónica) calculado\n'
            'no coincide con el esperado por la DIAN. Este es un error\n'
            'técnico que requiere intervención del equipo de soporte.'
        ),
        'category': 'technical',
        'fields': [],
    },
    {
        'code': 'CBF03a',
        'patterns': ['CBF03a', 'CustomizationID'],
        'message': 'CustomizationID incorrecto para el tipo de documento',
        'details': (
            'El código CustomizationID no corresponde al tipo de documento.\n'
            'Valores correctos: 10 (Factura), 20 (NC con ref), 22 (NC sin ref),\n'
            '30 (ND con ref), 32 (ND sin ref). Contactar soporte técnico.'
        ),
        'category': 'technical',
        'fields': [],
    },
    {
        'code': 'FAB36',
        'patterns': ['FAB36', 'QR Code', 'QRCode'],
        'message': 'QR Code faltante en el XML',
        'details': (
            'El XML enviado a la DIAN no contiene el QR Code obligatorio\n'
            'en la sección DianExtensions. Contactar soporte técnico.'
        ),
        'category': 'technical',
        'fields': [],
    },
    {
        'code': 'FAB31',
        'patterns': ['FAB31', 'AuthorizationProvider', '800197268'],
        'message': 'AuthorizationProvider faltante en DianExtensions',
        'details': (
            'Falta el bloque AuthorizationProvider con el NIT de la DIAN\n'
            '(800197268) en las extensiones del XML. Contactar soporte técnico.'
        ),
        'category': 'technical',
        'fields': [],
    },
    {
        'code': 'FBE01',
        'patterns': ['FBE01', 'AllowanceCharge'],
        'message': 'AllowanceCharge faltante en líneas del documento',
        'details': (
            'Las líneas de detalle del documento no incluyen el bloque\n'
            'AllowanceCharge obligatorio (requerido incluso si es 0.00).\n'
            'Contactar soporte técnico.'
        ),
        'category': 'technical',
        'fields': [],
    },
    {
        'code': 'FAV05/FBB05',
        'patterns': ['FAV05', 'FBB05', 'unidad de la cantidad utilizada NO existe'],
        'message': 'Unidad de medida del producto inválida para la DIAN',
        'details': (
            'La Unidad de Medida configurada en el producto (ej. "E48") '
            'no está en el catálogo de la DIAN. Abra la configuración de Unidades, '
            'y cambie el código de la unidad a "94" (Unidades de comercio), '
            '"EA" (Cada Uno) o "NIU" según la Resolución DIAN.'
        ),
        'category': 'technical',
        'fields': [],
    },
    {
        'code': 'RUT01',
        'patterns': ['RUT01', 'estado del RUT próximamente'],
        'message': 'Aviso Técnico DIAN: Validación RUT (Ignorable)',
        'details': (
            'Esta es una advertencia inofensiva de la DIAN que NO bloquea '
            'la factura. Informan que pronto activarán validaciones de RUT '
            'en tiempo real. Si este es el único mensaje, su factura debería '
            'haber sido aceptada.'
        ),
        'category': 'technical',
        'fields': [],
    },
    {
        'code': 'Regla: 90',
        'patterns': ['Regla: 90', 'Regla 90', 'procesado anteriormente',
                     'documento duplicado', 'Duplicate'],
        'message': 'Documento ya procesado anteriormente (duplicado)',
        'details': (
            'La DIAN detectó que este número de documento ya fue enviado\n'
            'previamente. Cada consecutivo es irrepetible.\n'
            'Use "Resecuenciar" para asignar un nuevo número.'
        ),
        'category': 'technical',
        'fields': [],
    },
]


# =========================================================================
# SANITIZER — 2-layer HTML cleaning
# =========================================================================

def sanitize_dian_error(raw_error):
    """Sanitize a DIAN error message, stripping any HTML tags.

    Strategy (2 layers + final fallback):
      1. lxml.html.fromstring() + text_content() → best quality
      2. regex re.sub(r'<[^>]+>', '') → fallback if lxml fails
      3. html.escape() → last resort, escapes any remaining HTML

    :param raw_error: Raw error string (may contain HTML)
    :returns: Clean plain-text string, never None/empty
    """
    if not raw_error:
        return 'Error reportado por la DIAN (sin detalle)'

    raw_str = str(raw_error).strip()
    if not raw_str:
        return 'Error reportado por la DIAN (sin detalle)'

    # If the string doesn't look like HTML, return as-is
    if '<' not in raw_str:
        return raw_str

    # Layer 1: lxml (best quality — preserves text structure)
    if _HAS_LXML:
        try:
            doc_tree = lxml_html.fromstring(raw_str)
            clean = doc_tree.text_content().strip()
            if clean:
                return clean
        except Exception:
            pass

    # Layer 2: regex (fallback)
    try:
        clean = re.sub(r'<[^>]+>', ' ', raw_str)
        # Collapse multiple spaces
        clean = re.sub(r'\s+', ' ', clean).strip()
        if clean:
            return clean
    except Exception:
        pass

    # Layer 3: escape any remaining HTML to prevent injection
    return html.escape(raw_str)


# =========================================================================
# TRANSLATOR — Match error text against known rules
# =========================================================================

def translate_dian_error(clean_text):
    """Translate a clean DIAN error text into a user-friendly diagnosis.

    Searches the error text against known DIAN rule patterns.
    Returns the FIRST matching rule (rules are ordered by
    specificity/frequency).

    :param clean_text: Plain-text error message (already sanitized)
    :returns: dict with diagnosis info, or None if no match found

    Return dict structure::

        {
            'code': 'FAJ28',
            'message': 'Dirección del contacto incompleta...',
            'details': 'La DIAN requiere dirección completa...',
            'category': 'partner',
            'fields': ['city_id', 'state_id', ...],
        }
    """
    if not clean_text:
        return None

    text_upper = clean_text.upper()

    for rule in DIAN_ERROR_MAP:
        for pattern in rule['patterns']:
            if pattern.upper() in text_upper:
                return {
                    'code': rule['code'],
                    'message': rule['message'],
                    'details': rule['details'],
                    'category': rule['category'],
                    'fields': rule['fields'],
                }

    # No match found — caller should use the raw error as fallback
    return None
