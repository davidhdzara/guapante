{
    'name': 'Portal de Empleados Colombia',
    'version': '18.0.2.0.0',
    'category': 'Human Resources',
    'summary': 'Perfil y solicitudes auditables de actualización para empleados',
    'license': 'LGPL-3',
    # hr_payroll is used for payslips/contracts and NE for the accepted state.
    'depends': ['portal', 'website', 'hr', 'hr_payroll', 'l10n_co_nomina_electronica'],
    'data': [
        'security/portal_employee_security.xml',
        'security/ir.model.access.csv',
        'data/employee_certificate_sequence.xml',
        'views/employee_update_request_views.xml',
        'views/hr_employee_views.xml',
        'views/res_company_views.xml',
        'views/employee_certificate_issuance_views.xml',
        'report/employee_certificate_report.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}
