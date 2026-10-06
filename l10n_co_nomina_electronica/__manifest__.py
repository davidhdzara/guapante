{
    'name': 'Nómina Electrónica Colombia - DIAN',
    'version': '18.0.3.0.60',
    'category': 'Human Resources/Payroll',
    'summary': 'Generación y envío de Nómina Electrónica a la DIAN (Resolución 000013 de 2021)',
    'description': """
Nómina Electrónica Colombia - DIAN
===================================

Módulo completo para la generación y transmisión de la Nómina Electrónica
Individual y Notas de Ajuste ante la DIAN, conforme a la Resolución 000013
de 2021.

Funcionalidades principales:
- Generación de XML UBL 2.1 para Nómina Individual Electrónica
- Generación de Notas de Ajuste (Reemplazar / Eliminar)
- Firma digital XAdES-BES con certificado .p12
- Envío al WebService de la DIAN (habilitación y producción)
- Cálculo de CUNE (Código Único de Nómina Electrónica)
- Reportes UGPP (Unidad de Gestión Pensional y Parafiscales)
- Cálculo automático de Retención en la Fuente (Procedimiento 1 y 2)
- Provisiones automáticas (Prima, Cesantías, Intereses, Vacaciones) vía reglas invisibles
- Liquidación de contrato (cálculo automático)
- Integración con módulo de ausencias (hr.leave)
- Representación gráfica (PDF) con QR
- 40+ reglas salariales preconfiguradas
    """,
    'author': 'InSoTech - Infinity Solutions Technology S.A.S',
    'website': 'https://insotech.it',
    'license': 'LGPL-3',
    'depends': [
        'hr_payroll',
        'hr_payroll_account',
        'account',
        'l10n_co',
        'hr_holidays',
        'certificate',
    ],
    'external_dependencies': {
        'python': [
            'cryptography',
            'lxml',
            'requests',
            'openpyxl',
            'qrcode',
        ],
    },
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/l10n_co_ne_exchange_security.xml',
        # Data
        'data/ir_sequence_data.xml',
        'data/l10n_co_rule_parameters_data.xml',
        'data/hr_payroll_dashboard_warning_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/l10n_co_embargo_input_types_data.xml',
        'data/l10n_co_horas_extra_input_types_data.xml',
        'data/l10n_co_novedades_input_types_data.xml',
        'data/hr_payroll_structure_special_data.xml',
        'data/hr_salary_rule_auto_deductions.xml',
        'data/hr_retefuente_data.xml',
        'data/ir_cron_habilitacion.xml',
        'data/ir_cron_dian_status_recheck.xml',
        # Views
        'wizard/hr_payslip_send_views.xml',
        'wizard/l10n_co_ne_certification_wizard_views.xml',
        'views/l10n_co_ne_operation_mode_views.xml',
        # AUD-DIAN-34 (2026-10-04): hr_retefuente_views.xml debe cargar
        # ANTES de hr_salary_rule_views.xml -- define el menu
        # menu_l10n_co_nomina_colombia_config que hr_salary_rule_views.xml
        # usa como parent. Orden anterior rompia -i en instalacion
        # limpia (nunca se detecto porque siempre se probo sobre un
        # modulo ya instalado, -u en vez de -i).
        'views/hr_retefuente_views.xml',
        'views/hr_salary_rule_views.xml',
        # res_config_settings_views.xml debe cargar DESPUES de
        # hr_salary_rule_views.xml -- su boton "Abrir Cuentas
        # Contables" referencia action_hr_salary_rule_account_ne,
        # definida ahi.
        'views/res_config_settings_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_payslip_views.xml',
        'views/l10n_co_ne_exchange_views.xml',
        'views/l10n_co_nomina_ugpp_views.xml',
        'views/hr_salary_attachment_views.xml',
        'views/hr_contract_deductions_views.xml',
        'views/hr_contract_retefuente_views.xml',
        # Reports
        'report/hr_payslip_ne_report.xml',
        # Wizards
        'wizard/l10n_co_nomina_ugpp_wizard_views.xml',
        'wizard/hr_liquidacion_wizard_views.xml',
        'wizard/hr_pila_wizard_v2_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
