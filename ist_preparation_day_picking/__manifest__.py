{
    'name': 'Picking (Guapante)',
    'version': '18.0.1.1.0',
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
    # mrp_workorder (Taller, Enterprise/OEEL-1): se depende para reusar
    # sus clases y SCSS (o_mrp_display, o_mrp_display_record, la
    # animación de tarjeta, etc.) vía web.assets_backend — nunca se
    # copia ningún archivo suyo a este módulo (LGPL-3), solo se
    # reutilizan las clases en nuestras propias plantillas (David,
    # especificación visual 2026-10-23, punto 2).
    # stock: Fase D depende directo de stock.scrap/stock.group_stock_manager/
    # stock_scrap_form_view2 — ya llegaba transitivo por ist_preparation_day,
    # se declara directo porque ahora se referencia explícitamente.
    'depends': ['ist_preparation_day', 'mrp_workorder', 'stock'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_release_claims.xml',
        'views/preparation_day_form_views.xml',
        'views/preparation_day_picking_menus.xml',
        'views/hr_employee_config_views.xml',
        'views/preparation_day_product_claim_views.xml',
        'views/preparation_day_note_template_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ist_preparation_day_picking/static/src/js/preparation_picking_idle_watcher.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_install_menu.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_app.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_badge_patch.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_operator_header.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_claim_menu.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_weight_input.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_note_dialog.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_level1_display.xml',
            'ist_preparation_day_picking/static/src/js/preparation_picking_level1_display.js',
            'ist_preparation_day_picking/static/src/js/preparation_picking_level2_display.xml',
            'ist_preparation_day_picking/static/src/js/preparation_picking_level2_display.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
