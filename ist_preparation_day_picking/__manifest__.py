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
        'views/preparation_day_form_views.xml',
        'views/preparation_day_line_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
