{
    'name': 'Insotech DIAN Setup Wizard',
    'version': '18.0.2.1.0',
    'category': 'Accounting/Localizations',
    'summary': 'Habilitación DIAN directa — envío de set de pruebas '
               'via SOAP sin configuración previa en Odoo',
    'description': """
        Módulo de habilitación DIAN para facturación electrónica
        colombiana. Envía el set de pruebas directamente a la DIAN
        via SOAP con datos emulados, sin requerir configuración
        previa de productos, contactos, ni categorías en Odoo.

        Características:
        - Captura de credenciales DIAN (Software ID, PIN, Test Set ID)
        - Generación de XMLs UBL 2.1 con datos emulados
        - Firma XAdES-BES con certificado .p12
        - Envío via SOAP (SendTestSetAsync)
        - Consulta de estado (GetStatusZip)
        - Cero dependencias de configuración Odoo
    """,
    'author': 'Insotech',
    'website': 'https://www.insotech.it',
    'depends': [
        'base',
        'mail',
        'account',
        'product',
        'l10n_co_dian',
        'insotech_core',
    ],
    'external_dependencies': {
        'python': ['lxml', 'cryptography', 'requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/cron_certificate_expiry.xml',
        'views/dian_setup_wizard_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}
