{
    'name': 'Picking (Guapante)',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Pantalla kanban a pantalla completa para pesaje de Picking',
    'description': """
        Pantalla de trabajo para Picking: kanban a pantalla completa de las
        líneas pendientes de la sesión activa de Preparación del Día,
        reutilizando el widget de báscula y la identificación por PIN ya
        existentes en ist_preparation_day. Restringido a un grupo dedicado
        (Guapante: Operación Picking) para no abrir el menú a todos los
        usuarios internos.
    """,
    'author': 'InSoTech',
    'website': 'https://www.insotech.com',
    'depends': ['ist_preparation_day'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/preparation_day_form_views.xml',
        'views/preparation_day_line_picking_views.xml',
        'views/preparation_day_picking_menus.xml',
        'views/hr_employee_config_views.xml',
        'views/preparation_day_product_claim_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ist_preparation_day_picking/static/src/js/preparation_picking_idle_watcher.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_app.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_badge_patch.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_claims_kanban.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
