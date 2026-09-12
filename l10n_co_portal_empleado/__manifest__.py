{
    'name': 'Portal de Empleados Colombia',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Perfil y solicitudes auditables de actualización para empleados',
    'license': 'LGPL-3',
    'depends': ['portal', 'website', 'hr'],
    'data': [
        'security/portal_employee_security.xml',
        'security/ir.model.access.csv',
        'views/employee_update_request_views.xml',
        'views/hr_employee_views.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}
