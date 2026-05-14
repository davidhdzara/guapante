{
    'name': 'Guapante MCP — Asistente por WhatsApp',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Chatbot IA en WhatsApp con autenticación por teléfono + NIT',
    'description': """
        Integra el MCP de Guapante con el módulo de WhatsApp de Odoo 18.
        Los clientes pueden consultar sus facturas, pedidos y solicitar acciones
        directamente desde WhatsApp, autenticándose con su número de teléfono y NIT.

        Características:
        - Autenticación segura: teléfono (WhatsApp) + NIT (sin depender de email)
        - Sesiones de 30 minutos con historial de conversación
        - Integración con Claude API (Anthropic) para lenguaje natural
        - Herramientas disponibles: facturas, saldos, pedidos, reenvío de facturas
        - Panel administrativo de sesiones activas
    """,
    'author': 'Insotech / Guapante',
    'depends': [
        'guapante_mcp_server',
        'mail',
        'whatsapp',
    ],
    'external_dependencies': {'python': ['anthropic']},
    'data': [
        'security/ir.model.access.csv',
        'data/mcp_whatsapp_params.xml',
        'views/whatsapp_session_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
