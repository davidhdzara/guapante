{
    'name': 'Guapante - Análisis de Ganancia Diaria',
    'version': '18.0.1.0.0',
    'category': 'Sales/Reporting',
    'summary': 'Reporte de ganancia diaria en ventas basado en el costo al momento de la venta.',
    'description': """
        Este módulo agrega un reporte de análisis de ganancia diaria.
        Utiliza el campo purchase_price de sale_margin para congelar el costo de venta.
        Vistas disponibles: Pivot (estilo Kardex), Graph, List.
        Accesible desde Contabilidad y Ventas.
    """,
    'author': 'InSoTech',
    'depends': ['account', 'sale_margin'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_profit_analysis_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
