{
    'name': 'Insotech — Tirilla Factura Electrónica POS',
    'version': '18.0.1.0.1',
    'category': 'Sales/Point of Sale',
    'summary': 'Formato DIAN para tirilla de recibo en Punto de Venta',
    'description': """
        Extiende la tirilla del recibo del Punto de Venta de Odoo 18 para mostrar 
        la información requerida por la DIAN para la Representación Gráfica de la 
        Factura Electrónica de Venta (Resolución 165):
        
        - Título "Factura Electrónica de Venta"
        - Resolución de numeración autorizada
        - Actividad Económica (CIIU)
        - Responsabilidades Fiscales
        - Forma y Medio de Pago (Anexo 1.9)
        - CUFE y Código QR de la DIAN
        - Aviso legal de datos personales
        - Datos del proveedor tecnológico
    """,
    'author': 'Insotech',
    'website': 'https://www.insotech.it',
    'depends': [
        'point_of_sale',
        'l10n_co_pos',
    ],
    'data': [],
    'assets': {
        'point_of_sale._assets_pos': [
            'insotech_l10n_co_pos/static/src/xml/pos_receipt.xml',
            'insotech_l10n_co_pos/static/src/js/pos_receipt.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
