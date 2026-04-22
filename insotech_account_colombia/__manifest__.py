{
    'name': 'InSoTech Localización Contable - Motor de Retenciones',
    'version': '1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Motor inteligente de retenciones para Colombia basado en UVT',
    'description': """
Módulo avanzado para el control de retenciones tributarias en Colombia.
Características:
- Tabla histórica de UVT para inmutabilidad contable.
- Configurador de Conceptos de Retención (Bases y Tarifas).
- (Fase 2) Inyección de retenciones en facturas.
- (Fase 3) Asistente nativo para cruce en pagos.
    """,
    'author': 'InSoTech / Antigravity',
    'depends': ['account', 'l10n_co'],
    'data': [
        'security/ir.model.access.csv',
        'views/insotech_uvt_views.xml',
        'views/insotech_retention_concept_views.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
