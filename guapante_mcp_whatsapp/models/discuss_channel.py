# -*- coding: utf-8 -*-
import json
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

_WELCOME_MSG = (
    "¡Hola! Soy el asistente de Comercializadora Guapante. 🌿\n\n"
    "Para consultar tus facturas y pedidos necesito verificar tu identidad.\n"
    "Por favor escribe tu *NIT* (sin dígito de verificación):"
)
_NIT_NOT_FOUND_MSG = (
    "No encontré un cliente registrado con ese NIT. "
    "Por favor verifica e intenta de nuevo. ({tries}/3)"
)
_NIT_CONFIRM_MSG = (
    "Encontré el cliente: *{name}*.\n"
    "¿Este número de WhatsApp es tuyo? Responde *sí* o *no*."
)
_AUTH_SUCCESS_MSG = (
    "✅ Identidad verificada. ¡Bienvenido, {name}!\n\n"
    "Puedo ayudarte con:\n"
    "• Ver tus facturas y saldo pendiente\n"
    "• Consultar tus pedidos\n"
    "• Solicitar el reenvío de una factura\n"
    "• Obtener el link de pago\n\n"
    "¿En qué te puedo ayudar hoy?"
)
_BLOCKED_MSG = (
    "🔒 Demasiados intentos fallidos. "
    "Comunícate con nuestro equipo para asistencia."
)
_RESET_KEYWORDS = ('salir', 'reiniciar', 'reset', 'logout', 'inicio')
_CONFIRM_YES = ('sí', 'si', 'yes', 's', 'claro', 'correcto', 'ok', 'afirmativo')
_CONFIRM_NO = ('no', 'nop', 'negativo', 'incorrecto')

# Tools available to the WhatsApp chatbot (user scope)
_WA_TOOLS = [
    {
        'name': 'list_invoices',
        'description': (
            'Lista las facturas de ventas del cliente autenticado. '
            'Muestra nombre, fecha, total y estado de pago.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'state': {
                    'type': 'string',
                    'enum': ['not_paid', 'paid', 'partial', 'in_payment'],
                    'description': 'Filtrar por estado de pago (opcional)',
                },
                'limit': {'type': 'integer', 'default': 5, 'maximum': 10},
            },
        },
    },
    {
        'name': 'get_invoice',
        'description': 'Obtiene el detalle de una factura específica del cliente.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'invoice_id': {'type': 'integer', 'description': 'ID de la factura'},
            },
            'required': ['invoice_id'],
        },
    },
    {
        'name': 'get_outstanding_balance',
        'description': 'Retorna el saldo pendiente y facturas vencidas del cliente.',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'list_orders',
        'description': 'Lista los pedidos de venta del cliente.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'state': {
                    'type': 'string',
                    'enum': ['draft', 'sent', 'sale', 'done'],
                },
                'limit': {'type': 'integer', 'default': 5, 'maximum': 10},
            },
        },
    },
    {
        'name': 'get_order',
        'description': 'Obtiene el detalle de un pedido específico del cliente.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'order_id': {'type': 'integer'},
            },
            'required': ['order_id'],
        },
    },
    {
        'name': 'send_invoice_email',
        'description': (
            'Envía la factura al email del cliente. '
            'Usar cuando el cliente pide que le reenvíen o envíen una factura.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'invoice_id': {'type': 'integer'},
            },
            'required': ['invoice_id'],
        },
    },
    {
        'name': 'get_payment_link',
        'description': 'Retorna el link de pago del portal para una factura.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'invoice_id': {'type': 'integer'},
            },
            'required': ['invoice_id'],
        },
    },
]


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    # ------------------------------------------------------------------
    # Entry point — override message_post for WhatsApp channels
    # ------------------------------------------------------------------

    def message_post(self, **kwargs):
        """Intercept incoming messages on WhatsApp channels to drive the bot."""
        result = super().message_post(**kwargs)

        # Only process WhatsApp channels and only incoming customer messages
        if (
            self.channel_type != 'whatsapp'
            or not result
            or kwargs.get('message_type') == 'notification'
            or kwargs.get('subtype_xmlid') == 'mail.mt_note'
        ):
            return result

        author = kwargs.get('author_id') or (result.author_id.id if result else False)
        bot_user = self.env.ref(
            'guapante_mcp_whatsapp.mcp_whatsapp_bot_partner',
            raise_if_not_found=False,
        )
        # Skip messages posted by the bot itself
        if bot_user and author == bot_user.id:
            return result

        # Skip messages from internal users
        author_partner = self.env['res.partner'].browse(author)
        if author_partner.user_ids.filtered(lambda u: u.share is False):
            return result

        body = kwargs.get('body', '')
        if hasattr(body, '__html__'):
            body = body
        body_text = (body or '').strip()
        if not body_text:
            return result

        # Determine WhatsApp number from channel context
        whatsapp_number = self._get_whatsapp_number()
        if not whatsapp_number:
            return result

        try:
            self._mcp_process_message(whatsapp_number, body_text)
        except Exception:
            _logger.exception(
                "MCP WhatsApp bot error on channel %s", self.id
            )

        return result

    def _get_whatsapp_number(self):
        """Extract the WhatsApp number from channel metadata."""
        # In Odoo 18, WhatsApp channels store the number in whatsapp_number or
        # in the channel partner's mobile. Try multiple strategies.
        if hasattr(self, 'whatsapp_number') and self.whatsapp_number:
            return self.whatsapp_number
        # Fallback: use the non-internal partner's mobile
        for member in self.channel_member_ids:
            partner = member.partner_id
            if partner and not partner.user_ids.filtered(lambda u: not u.share):
                return partner.mobile or partner.phone or ''
        return ''

    # ------------------------------------------------------------------
    # Bot message processing
    # ------------------------------------------------------------------

    def _mcp_process_message(self, whatsapp_number, body_text):
        """Main bot logic: auth state machine + Claude integration."""
        Session = self.env['guapante.mcp.whatsapp.session']
        session = Session._get_or_create_session(
            whatsapp_number, channel_id=self.id
        )

        # Allow reset at any point
        if body_text.lower() in _RESET_KEYWORDS:
            session.reset()
            self._bot_reply(_WELCOME_MSG)
            return

        if session.state == 'pending_nit':
            self._handle_pending_nit(session, body_text)
        elif session.state == 'pending_confirm':
            self._handle_pending_confirm(session, body_text)
        elif session.state == 'authenticated':
            self._handle_authenticated(session, body_text)
        elif session.state == 'blocked':
            self._bot_reply(_BLOCKED_MSG)
        else:
            session.reset()
            self._bot_reply(_WELCOME_MSG)

    def _handle_pending_nit(self, session, nit_text):
        """State: waiting for the customer to provide their NIT."""
        nit_clean = nit_text.strip().replace('.', '').replace('-', '').replace(' ', '')
        if not nit_clean.isdigit():
            self._bot_reply(
                "Por favor ingresa solo el número de NIT (sin puntos ni guiones)."
            )
            return

        partner = self.env['res.partner'].sudo().search(
            [('vat', '=', nit_clean), ('active', '=', True)],
            limit=1,
            order='id asc',
        )

        if not partner:
            tries = session.nit_tries + 1
            if tries >= 3:
                session.sudo().write({'state': 'blocked', 'nit_tries': tries})
                self._bot_reply(_BLOCKED_MSG)
                return
            session.sudo().write({'nit_tries': tries, 'nit_attempt': nit_clean})
            self._bot_reply(_NIT_NOT_FOUND_MSG.format(tries=tries))
            return

        # Check if the WhatsApp number matches the registered partner phone
        registered_phones = {
            (p or '').replace('+', '').replace(' ', '').replace('-', '')
            for p in [partner.mobile or '', partner.phone or '']
            if p
        }
        caller_number = (session.whatsapp_number or '').replace('+', '').replace(' ', '')

        if any(caller_number.endswith(p[-9:]) for p in registered_phones if len(p) >= 9):
            # Phone matches → auto-authenticate
            session.sudo().write({
                'state': 'authenticated',
                'partner_id': partner.id,
                'nit_tries': 0,
            })
            self._bot_reply(_AUTH_SUCCESS_MSG.format(name=partner.name))
        else:
            # Phone not on file → ask for confirmation and update if user agrees
            session.sudo().write({
                'state': 'pending_confirm',
                'partner_id': partner.id,
                'nit_attempt': nit_clean,
                'nit_tries': 0,
            })
            self._bot_reply(_NIT_CONFIRM_MSG.format(name=partner.name))

    def _handle_pending_confirm(self, session, body_text):
        """State: phone not on file, asking user to confirm they own the number."""
        text_lower = body_text.lower().strip()
        if text_lower in _CONFIRM_YES:
            partner = session.partner_id
            # Save WhatsApp number to partner mobile for future auto-auth
            if partner and not partner.mobile:
                partner.sudo().write({'mobile': session.whatsapp_number})
            session.sudo().write({'state': 'authenticated', 'nit_tries': 0})
            self._bot_reply(_AUTH_SUCCESS_MSG.format(name=partner.name))
        elif text_lower in _CONFIRM_NO:
            session.reset()
            self._bot_reply(
                "Entendido. Por favor ingresa el NIT correcto:"
            )
        else:
            self._bot_reply(
                "Por favor responde *sí* si este número es tuyo, o *no* para corregir el NIT."
            )

    def _handle_authenticated(self, session, user_message):
        """State: authenticated. Forward message to Claude with tools."""
        session.sudo().write({'message_count': session.message_count + 1})
        try:
            response = self._call_claude(session, user_message)
        except Exception as e:
            _logger.error("MCP WhatsApp Claude error: %s", e)
            response = (
                "Lo siento, tuve un problema procesando tu solicitud. "
                "Por favor intenta de nuevo."
            )
        self._bot_reply(response)

    # ------------------------------------------------------------------
    # Claude API integration
    # ------------------------------------------------------------------

    def _call_claude(self, session, user_message):
        """Call Claude API with tool_use and return the final text response."""
        import anthropic  # noqa: PLC0415 — optional dependency

        ICP = self.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('guapante_mcp_whatsapp.anthropic_api_key', '')
        model = ICP.get_param('guapante_mcp_whatsapp.claude_model', 'claude-opus-4-7')

        if not api_key:
            _logger.error("MCP WhatsApp: anthropic_api_key not configured")
            return "Servicio de asistente no disponible en este momento."

        client = anthropic.Anthropic(api_key=api_key)
        partner = session.partner_id

        system_prompt = (
            f"Eres el asistente de facturación de Comercializadora Guapante. "
            f"Cliente autenticado: {partner.name} "
            f"(NIT: {partner.vat or 'N/A'}, ID Odoo: {partner.id}). "
            f"Responde siempre en español. Sé conciso (máx 3 párrafos). "
            f"Usa texto plano, sin markdown complejo (sin asteriscos dobles, sin ###). "
            f"Para montos usa formato colombiano (COP con puntos de miles). "
            f"Si el cliente pide una factura, primero lista sus facturas y luego "
            f"ofrece el reenvío o link de pago."
        )

        history = json.loads(session.conversation_history or '[]')
        history.append({'role': 'user', 'content': user_message})

        # Convert our tool definitions to Anthropic format
        anthropic_tools = [
            {
                'name': t['name'],
                'description': t['description'],
                'input_schema': t['input_schema'],
            }
            for t in _WA_TOOLS
        ]

        max_iterations = 5
        for _ in range(max_iterations):
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=history,
                tools=anthropic_tools,
            )

            if response.stop_reason == 'end_turn':
                final_text = ''
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_text += block.text
                history.append({'role': 'assistant', 'content': final_text})
                break

            if response.stop_reason == 'tool_use':
                assistant_content = [
                    b.model_dump() if hasattr(b, 'model_dump') else b
                    for b in response.content
                ]
                history.append({'role': 'assistant', 'content': assistant_content})

                tool_results = []
                for block in response.content:
                    if getattr(block, 'type', '') == 'tool_use':
                        tool_result = self._execute_wa_tool(
                            block.name, block.input, partner.id
                        )
                        tool_results.append({
                            'type': 'tool_result',
                            'tool_use_id': block.id,
                            'content': json.dumps(tool_result, default=str),
                        })
                history.append({'role': 'user', 'content': tool_results})
            else:
                break

        # Keep only the last 20 messages to avoid context bloat
        session.sudo().write({'conversation_history': json.dumps(history[-20:])})
        return final_text if 'final_text' in dir() else ''

    def _execute_wa_tool(self, tool_name, tool_input, partner_id):
        """Execute a tool call from Claude, enforcing partner isolation."""
        tools = self.env['guapante.mcp.tools'].sudo()
        partner_restricted = {
            'list_invoices', 'get_outstanding_balance', 'list_orders',
        }
        partner_filtered = {
            'get_invoice', 'get_order', 'get_payment_link', 'send_invoice_email',
        }

        safe_input = dict(tool_input or {})

        if tool_name in partner_restricted:
            safe_input['partner_id'] = partner_id
        elif tool_name in partner_filtered:
            safe_input['partner_id'] = partner_id

        method_name = f'tool_{tool_name}'
        if not hasattr(tools, method_name):
            return {'error': f'Herramienta {tool_name} no disponible.'}

        try:
            return getattr(tools, method_name)(**safe_input)
        except Exception as e:
            _logger.error("MCP WA tool %s error: %s", tool_name, e)
            return {'error': str(e)}

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _bot_reply(self, text):
        """Post a bot message to the channel, bypassing the bot intercept."""
        self.sudo().message_post(
            body=text,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
