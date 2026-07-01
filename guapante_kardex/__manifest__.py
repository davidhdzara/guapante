{
    'name': 'Kardex Guapante',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Reporte de Kardex Personalizado para Comercializadora Guapante',
    'description': """
        Genera un reporte de Kardex dinámico con las siguientes columnas:
        - Con cuánto inicié
        - Cuánto se compró
        - Cuánto se vendió
        - Total que debo tener
        - Total en inventario
        - Diferencia
    """,
    'author': 'InSoTech',
    'website': 'https://www.insotech.com',
    'depends': ['stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/kardex_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
