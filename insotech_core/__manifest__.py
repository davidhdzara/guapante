{
    'name': 'Insotech Core Licensing Engine',
    'version': '18.0.1.0.0',
    'category': 'Technical Settings',
    'summary': 'Motor base de licenciamiento SaaS para los módulos de Insotech',
    'description': """
        Módulo base e independiente que sirve como validador para que otros submódulos funcionen.
    """,
    'author': 'Insotech',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
