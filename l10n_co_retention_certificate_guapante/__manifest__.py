# -*- coding: utf-8 -*-
{
    'name': 'Certificado de Retenciones - Marca Guapante',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Identidad visual de Guapante para el Certificado de Retenciones',
    'description': """
Certificado de Retenciones - Marca Guapante
============================================

Extensión EXCLUSIVA de Comercializadora y Productora Guapante S.A.S.
sobre el módulo comercial l10n_co_retention_certificate (que se
distribuye a otros clientes de InSoTech sin ningún branding).

Este módulo NO debe copiarse a otros clientes ni publicarse en el
repositorio comercial (insotech_accounting) — vive únicamente en el
repositorio de despliegue de Guapante (guapante.git).

Reemplaza únicamente:
- El encabezado/pie del certificado (logo de theme_guapante en vez del
  logo/Document Layout genérico de Odoo).
- La paleta de colores del cuerpo (verde corporativo #14532d en vez de
  gris neutro).

No toca la lógica de datos, el clasificador de impuestos ni el wizard
del módulo base — mismo patrón de "bypass" que
insotech_document_layouts usa para facturas y recibos de pago.
    """,
    'author': 'InSoTech',
    'depends': ['l10n_co_retention_certificate'],
    'data': [
        'views/retention_certificate_layout_guapante.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
