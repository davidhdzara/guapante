{
    'name': 'Insotech MCP Server — Facturación y Órdenes',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Servidor MCP seguro para consulta y gestión de facturación y órdenes',
    'description': """
        Implementa el protocolo Model Context Protocol (MCP 2024-11-05) como un endpoint
        HTTP en Odoo, permitiendo a asistentes de IA (Claude Desktop, apps empresariales)
        consultar y actualizar información de facturación y órdenes de manera bidireccional.

        Características:
        - Endpoint POST /mcp/v1 con autenticación Bearer token (SHA-256)
        - Scopes granulares: admin (acceso total) y user (filtrado por partner)
        - Herramientas: facturas, órdenes, estado DIAN, retenciones colombianas
        - Auditoría completa de todas las llamadas
        - Panel administrativo para gestionar API keys
    """,
    'author': 'Insotech / Insotech',
    'depends': [
        'account',
        'insotech_account_colombia',
        'insotech_core',
        'insotech_l10n_co_advanced',
        'mail',
        'portal',
        'sale',
    ],
    'data': [
        'security/mcp_security.xml',
        'security/ir.model.access.csv',
        'data/mcp_config_data.xml',
        'views/mcp_api_key_views.xml',
        'views/mcp_tool_log_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}
