{
    'name': 'Preparación del Día (Guapante)',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Alistamiento de pedidos por producto, pesaje con identificación por PIN',
    'description': """
        Preparación del Día: agrupa los pedidos confirmados por producto para acelerar el
        empaque en bodega, con pesaje real identificado por operario (PIN) y métricas de
        rendimiento. Extraído de theme_guapante (2026-10-21) — no depende de él.
    """,
    'author': 'InSoTech',
    'website': 'https://www.insotech.com',
    'depends': ['base', 'stock', 'sale', 'stock_picking_batch', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/preparation_day_views.xml',
        'views/stock_picking_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ist_preparation_day/static/src/js/preparation_operator_state.js',
            'ist_preparation_day/static/src/js/preparation_operator_badge.js',
            'ist_preparation_day/static/src/js/preparation_list.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
