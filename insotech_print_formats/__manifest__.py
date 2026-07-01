{
    'name': 'InSoTech Print Formats - Guapante',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Custom print formats for invoices, payment receipts, and sale orders',
    'description': """
        Custom Guapante branded print formats:
        - Invoice document layout (B2B corporate design)
        - Payment receipt design
        - Sale order confirmation (WhatsApp format)
        
        This module ONLY handles print formats.
        It does NOT modify electronic invoicing or DIAN logic.
    """,
    'author': 'InSoTech',
    'website': 'https://insotech.co',
    'depends': [
        'account',
        'sale',
    ],
    'data': [
        'views/report_invoice_document_inherit.xml',
        'views/report_payment_receipt_inherit.xml',
        'views/report_saleorder_whatsapp.xml',
        'views/report_saleorder_document_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
