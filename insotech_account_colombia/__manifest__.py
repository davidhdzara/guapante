{
    'name': 'InSoTech Localización Contable - Motor de Retenciones',
    'version': '2.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Motor inteligente de retenciones para Colombia basado en UVT',
    'description': """
Módulo avanzado para el control de retenciones tributarias en Colombia.
Características:
- Tabla histórica de UVT para inmutabilidad contable.
- Configurador de Conceptos de Retención (Bases y Tarifas).
- Cálculo automático de retenciones en facturas de proveedor.
- Validación de obligaciones DIAN (Autorretenedor, Régimen Simple).
- (Fase 3) Asistente nativo para cruce en pagos.
    """,
    'author': 'InSoTech / Antigravity',
    'depends': ['account', 'l10n_co', 'l10n_co_edi', 'product', 'base_address_extended'],
    'data': [
        'security/ir.model.access.csv',
        'views/menuitems.xml',
        'views/insotech_uvt_views.xml',
        'views/insotech_retention_category_views.xml',
        'views/insotech_retention_concept_views.xml',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/report_invoice_retention_block.xml',
        'data/insotech_category_data.xml',
        'data/insotech_retention_server_actions.xml',
        'data/insotech_retention_mass_action.xml',
        'views/account_payment_register_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
