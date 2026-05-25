{
    'name': 'Insotech — Localización Colombiana Avanzada',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Protección de consecutivos DIAN y facturación electrónica segura para Colombia',
    'description': """
        Extiende la localización nativa colombiana para proteger los consecutivos
        de resolución DIAN contra rechazos técnicos y errores de datos.
    """,
    'author': 'Insotech',
    'website': 'https://www.insotech.it',
    'depends': [
        'account',
        'sale',
        'l10n_co_edi',
        'l10n_co_dian',
        'mail',
        'web',
        'insotech_core',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/account_move_views.xml',
        'views/account_journal_views.xml',
        'views/report_invoice_document_inherit.xml',
        'views/report_payment_receipt_inherit.xml',
        'views/report_saleorder_whatsapp.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
