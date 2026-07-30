# -*- coding: utf-8 -*-
{
    'name': 'Colombia - Certificado de Retenciones',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Certificado de retenciones por tercero (Fuente, IVA, ICA, Parafiscales)',
    'description': """
Colombia - Certificado de Retenciones
======================================

Certificado de retenciones practicadas a proveedores, agrupado por concepto
(impuesto) en lugar de por cuenta contable, para no depender de cómo esté
configurado el PUC de cada cliente.

- Clasificador automático de impuestos colombianos de retención
  (`account.tax`) en Retención en la Fuente / ReteIVA / ReteICA / Parafiscal.
- Reporte propio (account.report) con jerarquía Tercero → Tipo de Retención
  → Concepto. Menú: Contabilidad → Reportes → Estados de cuenta colombianos
  → Certificado de Retenciones.
- Emisión en PDF reutilizando el wizard nativo de l10n_co_reports (fechas
  de expedición/declaración + artículo); la selección de proveedores y de
  qué retenciones incluir se resuelve con el filtro de tercero y el estado
  de plegado/desplegado del reporte.
- Plantilla QWeb propia con secciones por tipo (Fuente/IVA/ICA/Parafiscal),
  cada una con su nota legal, sobre web.external_layout — respeta el
  Document Layout y el logo que cada cliente configure, sin branding
  hardcodeado. Un cliente que necesite identidad visual propia debe
  construir un módulo de extensión aparte (ver README).
    """,
    'author': 'David Hernández',
    'website': 'https://github.com/davidhdzara/insotech_accounting',
    'license': 'LGPL-3',
    'depends': ['account_reports', 'l10n_co', 'l10n_co_reports'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_tax_views.xml',
        'data/retention_certificate_report.xml',
        'report/retention_certificate_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
