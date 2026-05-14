# -*- coding: utf-8 -*-
import json
import logging
import time

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = '2024-11-05'
MCP_SERVER_NAME = 'guapante-mcp-server'
MCP_SERVER_VERSION = '1.0.0'

# Tools available per scope. Each entry: (name, description, input_schema, admin_only)
_TOOL_DEFINITIONS = [
    (
        'list_invoices',
        'Lista las facturas de ventas (out_invoice/out_refund) del sistema Odoo de Guapante.',
        {
            'type': 'object',
            'properties': {
                'partner_id': {'type': 'integer', 'description': 'ID del cliente en Odoo'},
                'state': {
                    'type': 'string',
                    'enum': ['not_paid', 'paid', 'partial', 'in_payment', 'reversed'],
                    'description': 'Estado de pago',
                },
                'date_from': {'type': 'string', 'format': 'date', 'description': 'Desde (YYYY-MM-DD)'},
                'date_to': {'type': 'string', 'format': 'date', 'description': 'Hasta (YYYY-MM-DD)'},
                'limit': {'type': 'integer', 'default': 20, 'maximum': 50},
            },
        },
        False,
    ),
    (
        'get_invoice',
        'Obtiene el detalle completo de una factura: líneas, impuestos, estado DIAN, CUFE y URL de portal.',
        {
            'type': 'object',
            'properties': {
                'invoice_id': {'type': 'integer', 'description': 'ID de la factura en Odoo'},
            },
            'required': ['invoice_id'],
        },
        False,
    ),
    (
        'get_outstanding_balance',
        'Retorna el saldo pendiente y las facturas vencidas de un cliente.',
        {
            'type': 'object',
            'properties': {
                'partner_id': {'type': 'integer', 'description': 'ID del partner en Odoo'},
            },
            'required': ['partner_id'],
        },
        False,
    ),
    (
        'get_payment_link',
        'Retorna la URL del portal de pagos para una factura específica.',
        {
            'type': 'object',
            'properties': {
                'invoice_id': {'type': 'integer', 'description': 'ID de la factura'},
            },
            'required': ['invoice_id'],
        },
        False,
    ),
    (
        'list_orders',
        'Lista los pedidos de venta del sistema.',
        {
            'type': 'object',
            'properties': {
                'partner_id': {'type': 'integer', 'description': 'ID del cliente'},
                'state': {
                    'type': 'string',
                    'enum': ['draft', 'sent', 'sale', 'done', 'cancel'],
                },
                'date_from': {'type': 'string', 'format': 'date'},
                'date_to': {'type': 'string', 'format': 'date'},
                'limit': {'type': 'integer', 'default': 20, 'maximum': 50},
            },
        },
        False,
    ),
    (
        'get_order',
        'Obtiene el detalle completo de un pedido: líneas, entregas y facturas vinculadas.',
        {
            'type': 'object',
            'properties': {
                'order_id': {'type': 'integer', 'description': 'ID del pedido en Odoo'},
            },
            'required': ['order_id'],
        },
        False,
    ),
    # Admin-only tools
    (
        'get_partner_statement',
        'Genera el estado de cuenta completo de un cliente en un rango de fechas.',
        {
            'type': 'object',
            'properties': {
                'partner_id': {'type': 'integer'},
                'date_from': {'type': 'string', 'format': 'date'},
                'date_to': {'type': 'string', 'format': 'date'},
            },
            'required': ['partner_id'],
        },
        True,
    ),
    (
        'get_retention_summary',
        'Retorna el resumen de retenciones (retefuente, reteica, reteiva, parafiscal) de un partner.',
        {
            'type': 'object',
            'properties': {
                'partner_id': {'type': 'integer'},
                'date_from': {'type': 'string', 'format': 'date'},
                'date_to': {'type': 'string', 'format': 'date'},
            },
            'required': ['partner_id'],
        },
        True,
    ),
    (
        'send_invoice_email',
        'Envía la factura electrónica al cliente por email (PDF + XML DIAN si aplica).',
        {
            'type': 'object',
            'properties': {
                'invoice_id': {'type': 'integer'},
            },
            'required': ['invoice_id'],
        },
        True,
    ),
    (
        'get_dian_status',
        'Consulta el estado DIAN de una factura electrónica (CUFE, estado, errores de rechazo).',
        {
            'type': 'object',
            'properties': {
                'invoice_id': {'type': 'integer'},
            },
            'required': ['invoice_id'],
        },
        True,
    ),
    (
        'add_invoice_note',
        'Agrega una nota interna en el chatter de una factura.',
        {
            'type': 'object',
            'properties': {
                'invoice_id': {'type': 'integer'},
                'note': {'type': 'string', 'description': 'Texto de la nota'},
            },
            'required': ['invoice_id', 'note'],
        },
        True,
    ),
    # Product & order write tools
    (
        'search_products',
        'Busca productos por nombre y retorna atributos disponibles y unidades de medida validas.',
        {
            'type': 'object',
            'properties': {
                'query': {'type': 'string'},
                'limit': {'type': 'integer', 'default': 10, 'maximum': 20},
            },
            'required': ['query'],
        },
        False,
    ),
    (
        'get_active_orders',
        'Retorna ordenes confirmadas del partner donde el picking no ha iniciado.',
        {
            'type': 'object',
            'properties': {
                'partner_id': {'type': 'integer'},
            },
            'required': ['partner_id'],
        },
        False,
    ),
    (
        'create_confirmed_order',
        'Crea y confirma una orden de venta, luego envia el comprobante por WhatsApp.',
        {
            'type': 'object',
            'properties': {
                'partner_id': {'type': 'integer'},
                'lines': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'product_name': {'type': 'string'},
                            'attributes': {'type': 'object'},
                            'quantity': {'type': 'number'},
                            'uom_name': {'type': 'string'},
                        },
                        'required': ['product_name', 'quantity', 'uom_name'],
                    },
                },
            },
            'required': ['partner_id', 'lines'],
        },
        True,
    ),
    (
        'add_line_to_order',
        'Agrega lineas a una orden confirmada donde el alistamiento no ha iniciado.',
        {
            'type': 'object',
            'properties': {
                'order_id': {'type': 'integer'},
                'partner_id': {'type': 'integer'},
                'lines': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'product_name': {'type': 'string'},
                            'attributes': {'type': 'object'},
                            'quantity': {'type': 'number'},
                            'uom_name': {'type': 'string'},
                        },
                        'required': ['product_name', 'quantity', 'uom_name'],
                    },
                },
            },
            'required': ['order_id', 'partner_id', 'lines'],
        },
        True,
    ),
]


def _cors_headers():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Authorization, Content-Type',
        'Content-Type': 'application/json',
    }


def _json_response(data, status=200):
    return Response(
        json.dumps(data),
        status=status,
        headers=_cors_headers(),
    )


def _error_response(req_id, code, message):
    return _json_response({
        'jsonrpc': '2.0',
        'error': {'code': code, 'message': message},
        'id': req_id,
    })


class GuapanteMcpController(http.Controller):

    @http.route('/mcp/v1', type='http', auth='none', methods=['OPTIONS'], csrf=False)
    def mcp_options(self, **kwargs):
        return Response('', status=204, headers=_cors_headers())

    @http.route('/mcp/v1', type='http', auth='none', methods=['POST'], csrf=False)
    def mcp_endpoint(self, **kwargs):
        t_start = time.monotonic()
        req_id = None
        api_key = None

        try:
            # 1. Parse JSON body
            try:
                body = json.loads(request.httprequest.data or '{}')
            except json.JSONDecodeError:
                return _error_response(None, -32700, 'Parse error: invalid JSON')

            req_id = body.get('id')
            method = body.get('method', '')
            params = body.get('params') or {}

            # 2. Validate Bearer token (except for initialize which must also be authenticated)
            auth_header = request.httprequest.headers.get('Authorization', '')
            raw_token = ''
            if auth_header.startswith('Bearer '):
                raw_token = auth_header[7:].strip()

            api_key = request.env['guapante.mcp.api.key']._validate_token(raw_token)
            if not api_key:
                return _error_response(req_id, -32001, 'Unauthorized: invalid or expired token')

            # 3. Dispatch
            if method == 'initialize':
                result = self._handle_initialize(params)
            elif method == 'tools/list':
                result = self._handle_tools_list(api_key)
            elif method == 'tools/call':
                result = self._handle_tools_call(params, api_key, req_id, t_start)
                return result
            else:
                return _error_response(req_id, -32601, f'Method not found: {method}')

            return _json_response({'jsonrpc': '2.0', 'result': result, 'id': req_id})

        except Exception as e:
            _logger.exception("MCP endpoint unhandled error")
            return _error_response(req_id, -32603, f'Internal error: {str(e)}')

    def _handle_initialize(self, params):
        return {
            'protocolVersion': MCP_PROTOCOL_VERSION,
            'capabilities': {'tools': {}},
            'serverInfo': {
                'name': MCP_SERVER_NAME,
                'version': MCP_SERVER_VERSION,
            },
        }

    def _handle_tools_list(self, api_key):
        is_admin = api_key.scope == 'admin'
        tools = []
        for name, description, schema, admin_only in _TOOL_DEFINITIONS:
            if admin_only and not is_admin:
                continue
            tools.append({
                'name': name,
                'description': description,
                'inputSchema': schema,
            })
        return {'tools': tools}

    def _handle_tools_call(self, params, api_key, req_id, t_start):
        tool_name = params.get('name', '')
        arguments = params.get('arguments') or {}
        is_admin = api_key.scope == 'admin'
        ip = request.httprequest.remote_addr

        # Validate tool exists and scope
        tool_def = next((t for t in _TOOL_DEFINITIONS if t[0] == tool_name), None)
        if not tool_def:
            return _error_response(req_id, -32602, f'Unknown tool: {tool_name}')
        if tool_def[3] and not is_admin:
            return _error_response(req_id, -32001, f'Tool "{tool_name}" requires admin scope')

        # For user scope, inject partner_id restriction
        if not is_admin and api_key.partner_id:
            if tool_name in ('get_invoice', 'get_payment_link'):
                arguments['partner_id'] = api_key.partner_id.id
            elif tool_name in ('list_invoices', 'get_outstanding_balance', 'list_orders'):
                arguments['partner_id'] = api_key.partner_id.id
            elif tool_name == 'get_order':
                arguments['partner_id'] = api_key.partner_id.id

        success = True
        error_msg = ''
        result_data = {}

        try:
            tools = request.env['guapante.mcp.tools'].sudo()
            method_name = f'tool_{tool_name}'
            if not hasattr(tools, method_name):
                return _error_response(req_id, -32602, f'Tool method not implemented: {tool_name}')
            result_data = getattr(tools, method_name)(**arguments)
            if isinstance(result_data, dict) and 'error' in result_data:
                success = False
                error_msg = result_data['error']
        except Exception as e:
            _logger.exception("MCP tool execution error: %s", tool_name)
            success = False
            error_msg = str(e)
            result_data = {'error': error_msg}

        # Audit log
        duration_ms = int((time.monotonic() - t_start) * 1000)
        try:
            request.env['guapante.mcp.tool.log'].sudo().create({
                'api_key_id': api_key.id,
                'tool_name': tool_name,
                'scope': api_key.scope,
                'arguments': json.dumps(
                    {k: v for k, v in arguments.items() if k != 'partner_id'},
                    default=str,
                ),
                'response_summary': str(result_data)[:500],
                'duration_ms': duration_ms,
                'success': success,
                'error_message': error_msg or False,
                'ip_address': ip,
            })
        except Exception:
            _logger.warning("MCP audit log write failed", exc_info=True)

        content_text = json.dumps(result_data, default=str, ensure_ascii=False)
        return _json_response({
            'jsonrpc': '2.0',
            'result': {
                'content': [{'type': 'text', 'text': content_text}],
                'isError': not success,
            },
            'id': req_id,
        })
