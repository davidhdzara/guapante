# -*- coding: utf-8 -*-
{
    'name': 'Colombia - Reportes Contables Avanzados',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Balance de Prueba por Terceros para la localización colombiana',
    'description': """
Colombia - Reportes Contables Avanzados
========================================

Agrega reportes contables avanzados requeridos por la normatividad
y práctica contable colombiana:

* **Balance de Prueba por Terceros**: Reporte estándar colombiano que
  agrupa los movimientos contables por cuenta y tercero, mostrando
  NIT, Razón Social, Saldo Anterior, Débito, Crédito y Saldo Final.

Características:
- Estructura jerárquica: Cuenta → Terceros
- NIT formateado con dígito de verificación
- Tipo de documento (NIT, CC, CE, etc.)
- Saldo anterior calculado respetando año fiscal
- Filtros por fecha, diario, tercero, cuenta analítica
- Exportación a Excel y PDF
- Compatible con multi-compañía
    """,
    'author': 'David Hernández',
    'website': 'https://github.com/davidhdzara/insotech_accounting',
    'license': 'LGPL-3',
    'depends': [
        'account_reports',
        'l10n_co',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/partner_balance_report.xml',
        'data/menuitems.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
