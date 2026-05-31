# -*- coding: utf-8 -*-
{
    'name': 'Colombia - Archivos Planos Bancarios',
    'version': '18.0.1.2.0',
    'category': 'Accounting/Payment',
    'summary': 'Exportacion de archivos planos para pagos masivos en bancos colombianos',
    'description': """
Colombia - Archivos Planos Bancarios
=====================================

Modulo para generar archivos de dispersion de pagos compatibles con los
portales de pago masivo de los principales bancos colombianos. Permite
exportar pagos a proveedores y nomina sin salir de Odoo.

Bancos y formatos soportados
----------------------------
* Banco Davivienda - Formato Excel Estandar (.xlsx)
* Banco de Bogota - Formato ASCII ancho fijo 250 chars (.txt)
* Bancolombia - Formato PAB ASCII 264 chars (.txt) - recomendado
* Bancolombia - Formato SAP ASCII 95 chars (.txt) - legacy

Caracteristicas principales
---------------------------
* Validacion previa en tiempo real (errores antes de generar)
* Auditoria automatica de cada archivo generado
* Regeneracion sin perder historial
* Permisos granulares (Contabilidad y Nomina)
* Soporta pagos a proveedores y nomina
* Codigos ACH Colombia precargados (17 bancos)
* Sanitizacion automatica de caracteres especiales

Flujo de uso
------------
1. Contabilidad > Proveedores > Pagos
2. Seleccionar pagos publicados
3. Accion > Exportar Archivo Plano Bancario
4. Elegir banco y revisar validacion
5. Generar y descargar archivo
6. Subir al portal del banco

Documentacion completa
----------------------
Ver README.md en:
https://github.com/davidhdzara/l10n_co_bank_payment_export
    """,
    'author': 'davidhdzara',
    'website': 'https://github.com/davidhdzara/l10n_co_bank_payment_export',
    'license': 'OPL-1',
    'depends': [
        'account',
        'account_accountant',
        'hr_payroll',
        'l10n_co',
        'mail',
    ],
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/res_bank_data.xml',
        'views/res_bank_views.xml',
        'views/bank_payment_export_views.xml',
        'wizard/bank_payment_export_wizard_views.xml',
    ],
    'demo': [],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
