{
    'name': 'Insotech — Localización Colombiana POS',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Adaptación de POS para Facturación Electrónica en Tirilla (DIAN)',
    'description': """
        Extiende el Punto de Venta de Odoo para emitir Facturas Electrónicas de Venta (Tipo 01)
        impresas en formato de tirilla térmica, cumpliendo con los requisitos de 
        Representación Gráfica de la DIAN (Resolución 165).

        Características principales:
        - Auto-asignación de "Consumidor Final" (NIT 222222222222).
        - Impresión del CUFE y Código QR de la DIAN en el tiquete JS.
        - Desglose de impuestos (INC, Base Gravable).
        - Información de Resolución y Proveedor Tecnológico.
        - Mapeo de métodos de pago (Efectivo, Tarjeta).
    """,
    'author': 'Insotech',
    'website': 'https://www.insotech.it',
    'depends': [
        'point_of_sale',
        'l10n_co_edi',
        'insotech_l10n_co_advanced',
    ],
    'data': [
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'insotech_l10n_co_pos/static/src/xml/pos_receipt.xml',
            'insotech_l10n_co_pos/static/src/js/pos_receipt.js',
            'insotech_l10n_co_pos/static/src/js/pos_payment_screen.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
