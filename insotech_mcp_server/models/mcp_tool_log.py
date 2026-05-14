# -*- coding: utf-8 -*-
from odoo import fields, models


class InsotechMcpToolLog(models.Model):
    _name = 'insotech.mcp.tool.log'
    _description = 'Insotech MCP Audit Log'
    _order = 'create_date desc'

    api_key_id = fields.Many2one(
        'insotech.mcp.api.key',
        string='API Key',
        ondelete='set null',
        index=True,
    )
    tool_name = fields.Char(string='Herramienta', required=True, index=True)
    scope = fields.Char(string='Scope', readonly=True)
    arguments = fields.Text(string='Argumentos (JSON)')
    response_summary = fields.Text(string='Resumen de Respuesta')
    duration_ms = fields.Integer(string='Duración (ms)')
    success = fields.Boolean(string='Exitosa', default=True)
    error_message = fields.Text(string='Error')
    ip_address = fields.Char(string='IP del Cliente')
