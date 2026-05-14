# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import _, api, models

_logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Bot messages
# -----------------------------------------------------------------------
_NIT_NOT_FOUND_MSG = (
    "No encontre un cliente registrado con el NIT {nit}. "
    "Verifica e intenta de nuevo. (Intento {tries}/3)"
)
_NIT_DV_MISMATCH_MSG = (
    "El digito de verificacion que ingresaste no coincide con el NIT. "
    "Intenta de nuevo. (Intento {tries}/3)"
)
_BRANCH_SELECTION_MSG = (
    "Hola! Encontre el cliente *{parent_name}*.\n\n"
    "Tengo registrados varios puntos con ese NIT. "
    "Desde cual estas haciendo el pedido?\n\n"
    "{options}\n\n"
    "Responde con el numero de tu punto."
)
_CONFIRM_NUMBER_MSG = (
    "Cliente verificado: *{name}*.\n"
    "Este es un numero nuevo para nosotros. "
    "Confirmas que este WhatsApp ({number}) es tuyo? "
    "Responde *si* o *no*."
)
_AUTH_SUCCESS_MSG = (
    "Identidad verificada. Bienvenido, {name}!\n\n"
    "Puedo ayudarte con:\n"
    "- Ver tus facturas y saldo pendiente\n"
    "- Consultar tus pedidos activos\n"
    "- Hacer un nuevo pedido o agregar productos\n"
    "- Solicitar el reenvio de una factura\n\n"
    "En que te puedo ayudar hoy?"
)
_BLOCKED_MSG = (
    "Demasiados intentos fallidos. "
    "Comunicate con nuestro equipo de ventas para asistencia."
)
_RESET_KEYWORDS = ('salir', 'reiniciar', 'reset', 'logout', 'inicio', 'menu')
_CONFIRM_YES = ('si', 'sí', 'yes', 's', 'claro', 'correcto', 'ok', 'afirmativo', 'dale')
_CONFIRM_NO = ('no', 'nop', 'negativo', 'incorrecto', 'n')
_ESCALATION_KEYWORDS = (
    'asesor', 'asesora', 'humano', 'humana', 'persona', 'agente',
    'ayuda', 'soporte', 'hablar con alguien', 'hablar con un asesor',
    'quiero hablar', 'necesito ayuda', 'no entiendo',
)

# -----------------------------------------------------------------------
# WhatsApp tools available to authenticated users (Claude tool_use format)
# -----------------------------------------------------------------------
_WA_TOOLS = [
    {
        'name': 'list_invoices',
        'description': (
            'Lista las facturas del cliente autenticado. '
            'Retorna nombre, fecha, total y estado de pago. '
            'Usar cuando el cliente pregunte por sus facturas.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'state': {
                    'type': 'string',
                    'enum': ['not_paid', 'paid', 'partial', 'in_payment'],
                    'description': 'Filtrar por estado (opcional)',
                },
                'limit': {'type': 'integer', 'default': 5, 'maximum': 10},
            },
        },
    },
    {
        'name': 'get_invoice',
        'description': 'Detalle completo de una factura especifica del cliente.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'invoice_id': {'type': 'integer'},
            },
            'required': ['invoice_id'],
        },
    },
    {
        'name': 'get_outstanding_balance',
        'description': 'Saldo pendiente total y facturas vencidas del cliente.',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'get_payment_link',
        'description': 'Link de pago del portal para una factura.',
        'input_schema': {
            'type': 'object',
            'properties': {'invoice_id': {'type': 'integer'}},
            'required': ['invoice_id'],
        },
    },
    {
        'name': 'send_invoice_email',
        'description': (
            'Envia la factura al cliente por email. '
            'Usar cuando el cliente pida que le reenvien o manden una factura.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {'invoice_id': {'type': 'integer'}},
            'required': ['invoice_id'],
        },
    },
    {
        'name': 'get_active_orders',
        'description': (
            'Retorna las ordenes de venta confirmadas del cliente donde el '
            'alistamiento (picking) aun no ha iniciado. '
            'Llamar SIEMPRE antes de crear un pedido nuevo o agregar productos, '
            'para preguntar al cliente si quiere agregar a una orden existente.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'search_products',
        'description': (
            'Busca productos por nombre y retorna sus atributos disponibles '
            '(grado de madurez, tamano, etc.) y las unidades de medida validas. '
            'Llamar SIEMPRE antes de tomar el pedido de un producto para saber '
            'que atributos y UoMs hay que pedir al cliente.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Nombre o parte del nombre del producto',
                },
            },
            'required': ['query'],
        },
    },
    {
        'name': 'create_confirmed_order',
        'description': (
            'Crea una nueva orden de venta, la confirma y envia el comprobante '
            'por WhatsApp. Llamar SOLO despues de que el cliente haya confirmado '
            'el resumen completo del pedido.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'lines': {
                    'type': 'array',
                    'description': 'Lineas del pedido',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'product_name': {
                                'type': 'string',
                                'description': 'Nombre del producto',
                            },
                            'attributes': {
                                'type': 'object',
                                'description': (
                                    'Valores de atributos exactos como los retorna '
                                    'search_products. Ej: {"Grado de madurez": "Maduro"}'
                                ),
                            },
                            'quantity': {'type': 'number'},
                            'uom_name': {
                                'type': 'string',
                                'description': 'Unidad de medida exacta de search_products',
                            },
                        },
                        'required': ['product_name', 'quantity', 'uom_name'],
                    },
                },
            },
            'required': ['lines'],
        },
    },
    {
        'name': 'add_line_to_order',
        'description': (
            'Agrega una o mas lineas a una orden de venta existente (confirmada, '
            'sin picking iniciado). Llamar SOLO despues de confirmacion del cliente.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'order_id': {'type': 'integer'},
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
            'required': ['order_id', 'lines'],
        },
    },
    {
        'name': 'list_orders',
        'description': 'Lista los pedidos del cliente (todos los estados).',
        'input_schema': {
            'type': 'object',
            'properties': {
                'state': {
                    'type': 'string',
                    'enum': ['draft', 'sent', 'sale', 'done', 'cancel'],
                },
                'limit': {'type': 'integer', 'default': 5, 'maximum': 10},
            },
        },
    },
    {
        'name': 'get_order',
        'description': 'Detalle de un pedido especifico del cliente.',
        'input_schema': {
            'type': 'object',
            'properties': {'order_id': {'type': 'integer'}},
            'required': ['order_id'],
        },
    },
]

# -----------------------------------------------------------------------
# System prompt for Claude
# -----------------------------------------------------------------------
_SYSTEM_PROMPT_TEMPLATE = (
    "Eres {bot_name}, el asistente de facturacion y pedidos de {company_description}.\n"
    "Cliente autenticado: {name} (NIT: {vat}, ID Odoo: {partner_id}).\n\n"
    "REGLAS GENERALES:\n"
    "- Responde siempre en espanol. Canal: WhatsApp.\n"
    "- Texto plano y conciso. Sin markdown (sin **, sin ###). Listas con guion o numero.\n"
    "- Montos en formato colombiano: $1.250.000 COP.\n"
    "- Nunca inventes productos, precios ni atributos. Todo debe venir de las herramientas.\n\n"
    "FLUJO DE PEDIDOS (seguir estrictamente):\n"
    "1. Cuando el cliente quiera pedir o agregar productos, llama get_active_orders primero.\n"
    "   - Si hay ordenes activas: pregunta si agrega a una existente o crea una nueva.\n"
    "   - Si no hay ordenes activas: procede a crear una nueva.\n"
    "2. Para CADA producto mencionado, llama search_products con su nombre.\n"
    "   - Usa los atributos y UoMs que retorne la herramienta, no los inventes.\n"
    "   - Si el producto tiene atributos requeridos, pidelos UNO POR UNO de forma natural.\n"
    "   - Ejemplo: 'Que grado de madurez prefieres? Verde, Pinton o Maduro'\n"
    "   - Si la UoM no fue mencionada, preguntala mostrando las opciones disponibles.\n"
    "3. Acumula todas las lineas del pedido en la conversacion.\n"
    "4. Cuando el cliente diga que ya termino, muestra el RESUMEN COMPLETO:\n"
    "   - Lista cada linea: cantidad + UoM + producto + atributos\n"
    "   - Pregunta: 'Confirmas este pedido?'\n"
    "5. SOLO despues de confirmacion explicita del cliente:\n"
    "   - Si es orden nueva: llama create_confirmed_order.\n"
    "   - Si es agregar a existente: llama add_line_to_order.\n"
    "6. Despues de crear la orden, informa el numero de pedido generado.\n"
    "   El comprobante de WhatsApp se envia automaticamente.\n\n"
    "REGLAS DE SEGURIDAD:\n"
    "- Nunca muestres ni modifiques datos de otros clientes.\n"
    "- Si el cliente pide algo que no esta en las herramientas disponibles, disculpate "
    "y ofrece contactar al equipo de ventas."
)


# -----------------------------------------------------------------------
# NIT normalization
# -----------------------------------------------------------------------

def _normalize_nit(raw):
    """Extract the 9-digit NIT base from any Colombian NIT format.

    Handles: 900123456 / 900123456-1 / 9001234561 / 900.123.456 / 900.123.456-1
    Returns the numeric base without the verification digit.
    """
    base = raw.split('-')[0]
    digits = re.sub(r'\D', '', base)
    # If 10 digits, last digit is the DV — strip it
    if len(digits) == 10:
        digits = digits[:9]
    return digits


def _extract_dv(raw):
    """Return the verification digit if explicitly provided after a hyphen, else None."""
    if '-' in raw:
        parts = raw.split('-', 1)
        dv_part = re.sub(r'\D', '', parts[1])
        return dv_part if dv_part else None
    return None


# -----------------------------------------------------------------------
# Main model
# -----------------------------------------------------------------------

class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def message_post(self, **kwargs):
        result = super().message_post(**kwargs)

        if (
            self.channel_type != 'whatsapp'
            or not result
            or kwargs.get('message_type') == 'notification'
            or kwargs.get('subtype_xmlid') == 'mail.mt_note'
        ):
            return result

        author_id = kwargs.get('author_id') or (result.author_id.id if result else False)
        author_partner = self.env['res.partner'].browse(author_id)
        # Skip internal users
        if author_partner.user_ids.filtered(lambda u: not u.share):
            return result

        body_text = re.sub(r'<[^>]+>', '', str(kwargs.get('body', ''))).strip()
        if not body_text:
            return result

        whatsapp_number = self._get_whatsapp_number()
        if not whatsapp_number:
            return result

        try:
            self._wa_process_message(whatsapp_number, body_text)
        except Exception:
            _logger.exception("WA Assistant bot error on channel %s", self.id)

        return result

    def _get_whatsapp_number(self):
        if hasattr(self, 'whatsapp_number') and self.whatsapp_number:
            return self.whatsapp_number
        for member in self.channel_member_ids:
            partner = member.partner_id
            if partner and not partner.user_ids.filtered(lambda u: not u.share):
                return partner.mobile or partner.phone or ''
        return ''

    # ------------------------------------------------------------------
    # State machine dispatcher
    # ------------------------------------------------------------------

    def _wa_process_message(self, whatsapp_number, body_text):
        Session = self.env['insotech.wa.session']
        session = Session._get_or_create_session(whatsapp_number, channel_id=self.id)

        text_lower = body_text.lower().strip()

        if text_lower in _RESET_KEYWORDS:
            session.reset()
            self._bot_reply(self._get_welcome_msg())
            return

        if session.state == 'pending_nit':
            self._handle_pending_nit(session, body_text)
        elif session.state == 'pending_branch':
            self._handle_pending_branch(session, body_text)
        elif session.state == 'pending_confirm':
            self._handle_pending_confirm(session, body_text)
        elif session.state == 'authenticated':
            self._handle_authenticated(session, body_text)
        elif session.state == 'needs_human':
            self._handle_needs_human(session, body_text)
        elif session.state == 'blocked':
            self._bot_reply(_BLOCKED_MSG)
        else:
            session.reset()
            self._bot_reply(self._get_welcome_msg())

    # ------------------------------------------------------------------
    # Step 1 — NIT
    # ------------------------------------------------------------------

    def _handle_pending_nit(self, session, raw_text):
        raw_clean = raw_text.strip()
        nit_base = _normalize_nit(raw_clean)

        if not nit_base or not nit_base.isdigit() or len(nit_base) < 6:
            self._bot_reply(
                "Por favor ingresa solo el numero de NIT "
                "(sin puntos, sin espacios, sin digito de verificacion)."
            )
            return

        # Optional DV validation using insotech_core
        dv_provided = _extract_dv(raw_clean)
        if dv_provided:
            try:
                from odoo.addons.insotech_core.utils.dian import compute_dv
                dv_expected = compute_dv(nit_base)
                if dv_provided != str(dv_expected):
                    tries = session.nit_tries + 1
                    if tries >= 3:
                        session.sudo().write({'state': 'blocked', 'nit_tries': tries})
                        self._bot_reply(_BLOCKED_MSG)
                        return
                    session.sudo().write({'nit_tries': tries})
                    self._bot_reply(
                        _NIT_DV_MISMATCH_MSG.format(tries=tries)
                    )
                    return
            except ImportError:
                pass

        # Search parent partner by NIT (all common storage formats)
        partner = self.env['res.partner'].sudo().search(
            [
                ('vat', 'in', [nit_base, f'{nit_base}-{self._compute_dv_safe(nit_base)}']),
                ('parent_id', '=', False),
                ('active', '=', True),
            ],
            limit=1,
            order='id asc',
        )
        # Fallback: ilike search on vat starting with nit_base
        if not partner:
            partner = self.env['res.partner'].sudo().search(
                [
                    ('vat', 'like', nit_base),
                    ('parent_id', '=', False),
                    ('active', '=', True),
                ],
                limit=1,
                order='id asc',
            )

        if not partner:
            tries = session.nit_tries + 1
            if tries >= 3:
                session.sudo().write({'state': 'blocked', 'nit_tries': tries})
                self._bot_reply(_BLOCKED_MSG)
                return
            session.sudo().write({'nit_tries': tries, 'nit_attempt': nit_base})
            self._bot_reply(_NIT_NOT_FOUND_MSG.format(nit=nit_base, tries=tries))
            return

        # Find delivery address children
        children = self.env['res.partner'].sudo().search(
            [
                ('parent_id', '=', partner.id),
                ('active', '=', True),
                ('type', 'in', ['delivery', 'contact', 'other']),
            ],
            order='name asc',
        )

        if not children:
            # No children → authenticate as parent directly
            self._authenticate_partner(session, partner)
            return

        if len(children) == 1:
            # One child → skip selection, go to phone confirmation
            self._post_nit_auth(session, children[0])
            return

        # Multiple children → ask which branch
        options_data = [
            {
                'id': c.id,
                'name': c.name,
                'street': c.street or '',
                'city': c.city or '',
            }
            for c in children
        ]
        options_text = '\n'.join(
            f"{i + 1}. {o['name']}"
            + (f" - {o['street']}" if o['street'] else '')
            + (f", {o['city']}" if o['city'] else '')
            for i, o in enumerate(options_data)
        )
        session.sudo().write({
            'state': 'pending_branch',
            'nit_tries': 0,
            'pending_options': json.dumps(options_data),
        })
        self._bot_reply(
            _BRANCH_SELECTION_MSG.format(
                parent_name=partner.name,
                options=options_text,
            )
        )

    # ------------------------------------------------------------------
    # Step 2 — Branch selection
    # ------------------------------------------------------------------

    def _handle_pending_branch(self, session, body_text):
        options = json.loads(session.pending_options or '[]')
        if not options:
            session.reset()
            self._bot_reply(self._get_welcome_msg())
            return

        text = body_text.strip()
        selected = None

        # Accept numeric selection
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(options):
                selected = options[idx]

        # Accept partial name match
        if not selected:
            text_lower = text.lower()
            for opt in options:
                if text_lower in opt['name'].lower():
                    selected = opt
                    break

        if not selected:
            options_text = '\n'.join(
                f"{i + 1}. {o['name']}" for i, o in enumerate(options)
            )
            self._bot_reply(
                f"No entendi la seleccion. Por favor responde con el numero:\n\n"
                f"{options_text}"
            )
            return

        child = self.env['res.partner'].sudo().browse(selected['id'])
        self._post_nit_auth(session, child)

    # ------------------------------------------------------------------
    # Phone confirmation (after partner identified)
    # ------------------------------------------------------------------

    def _post_nit_auth(self, session, partner):
        """Check if the calling WhatsApp number matches the partner on file."""
        wa_number = session.whatsapp_number or ''
        registered = {
            re.sub(r'\D', '', p or '')
            for p in [partner.mobile or '', partner.phone or '']
            if p
        }
        wa_digits = re.sub(r'\D', '', wa_number)

        if any(
            wa_digits.endswith(r[-10:]) for r in registered if len(r) >= 10
        ):
            self._authenticate_partner(session, partner)
        else:
            session.sudo().write({
                'state': 'pending_confirm',
                'partner_id': partner.id,
                'pending_options': False,
                'nit_tries': 0,
            })
            self._bot_reply(
                _CONFIRM_NUMBER_MSG.format(
                    name=partner.name,
                    number=wa_number,
                )
            )

    def _authenticate_partner(self, session, partner):
        session.sudo().write({
            'state': 'authenticated',
            'partner_id': partner.id,
            'pending_options': False,
            'nit_tries': 0,
        })
        self._bot_reply(_AUTH_SUCCESS_MSG.format(name=partner.name))

    # ------------------------------------------------------------------
    # Step 3 — Phone confirmation
    # ------------------------------------------------------------------

    def _handle_pending_confirm(self, session, body_text):
        text_lower = body_text.lower().strip()
        if text_lower in _CONFIRM_YES:
            partner = session.partner_id
            if partner and not partner.mobile:
                partner.sudo().write({'mobile': session.whatsapp_number})
            self._authenticate_partner(session, partner)
        elif text_lower in _CONFIRM_NO:
            session.reset()
            self._bot_reply(
                "Entendido. Por favor ingresa el NIT correcto para continuar:"
            )
        else:
            self._bot_reply(
                "Por favor responde *si* si este numero es tuyo, o *no* para corregir."
            )

    # ------------------------------------------------------------------
    # Authenticated — forward to Claude
    # ------------------------------------------------------------------

    def _handle_authenticated(self, session, user_message):
        # Check escalation request before calling Claude
        text_lower = user_message.lower().strip()
        if any(kw in text_lower for kw in _ESCALATION_KEYWORDS):
            self._escalate_to_human(session, 'Solicitado por el cliente')
            return

        session.sudo().write({'message_count': session.message_count + 1})
        try:
            response = self._call_claude(session, user_message)
        except Exception as e:
            _logger.error("WA Assistant Claude error: %s", e)
            self._escalate_to_human(session, f'Error del asistente: {e}')
            return
        if response:
            self._bot_reply(response)

    # ------------------------------------------------------------------
    # Needs human — hold messages until released by admin
    # ------------------------------------------------------------------

    def _handle_needs_human(self, session, body_text):
        self._bot_reply(
            "Tu solicitud ya fue enviada a uno de nuestros asesores. "
            "Te contactarán a la brevedad. "
            "Escribe 'menu' si deseas reiniciar la sesion con el asistente."
        )

    # ------------------------------------------------------------------
    # Claude API
    # ------------------------------------------------------------------

    def _call_claude(self, session, user_message):
        import anthropic  # noqa: PLC0415

        ICP = self.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('insotech_wa_assistant.anthropic_api_key', '')
        model = ICP.get_param('insotech_wa_assistant.claude_model', 'claude-opus-4-7')

        if not api_key:
            _logger.error("WA Assistant: anthropic_api_key not configured")
            return "El servicio de asistente no esta disponible en este momento."

        client = anthropic.Anthropic(api_key=api_key)
        partner = session.partner_id
        bot_name = ICP.get_param('insotech_wa_assistant.bot_name', 'Asistente')
        company_description = ICP.get_param(
            'insotech_wa_assistant.company_description',
            self.env.company.name,
        )
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            bot_name=bot_name,
            company_description=company_description,
            name=partner.name,
            vat=partner.vat or 'N/A',
            partner_id=partner.id,
        )

        history = json.loads(session.conversation_history or '[]')
        history.append({'role': 'user', 'content': user_message})

        anthropic_tools = [
            {
                'name': t['name'],
                'description': t['description'],
                'input_schema': t['input_schema'],
            }
            for t in _WA_TOOLS
        ]

        final_text = ''
        for _ in range(8):  # max agentic iterations
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=history,
                tools=anthropic_tools,
            )

            if response.stop_reason == 'end_turn':
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_text += block.text
                history.append({'role': 'assistant', 'content': final_text})
                break

            if response.stop_reason == 'tool_use':
                assistant_content = []
                for block in response.content:
                    if hasattr(block, 'model_dump'):
                        assistant_content.append(block.model_dump())
                    else:
                        assistant_content.append(block)
                history.append({'role': 'assistant', 'content': assistant_content})

                tool_results = []
                for block in response.content:
                    if getattr(block, 'type', '') == 'tool_use':
                        result = self._execute_wa_tool(
                            block.name, block.input, session
                        )
                        tool_results.append({
                            'type': 'tool_result',
                            'tool_use_id': block.id,
                            'content': json.dumps(result, default=str),
                        })
                history.append({'role': 'user', 'content': tool_results})

        session.sudo().write({'conversation_history': json.dumps(history[-20:])})

        if not final_text:
            self._escalate_to_human(session, 'El asistente no pudo resolver la solicitud')
            return ''

        return final_text

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------

    def _escalate_to_human(self, session, reason):
        session.sudo().write({
            'state': 'needs_human',
            'escalation_reason': reason,
        })

        partner = session.partner_id
        partner_info = (
            f"{partner.name} ({session.whatsapp_number})"
            if partner
            else session.whatsapp_number
        )
        self._bot_reply(
            "Entendido. Voy a comunicarte con uno de nuestros asesores. "
            "Te contactarán a la brevedad. Gracias por tu paciencia."
        )

        # Notify escalation channel if configured
        ICP = self.env['ir.config_parameter'].sudo()
        channel_id = int(ICP.get_param('insotech_wa_assistant.escalation_channel_id', '0') or 0)
        if not channel_id:
            return
        escalation_channel = self.env['discuss.channel'].browse(channel_id).exists()
        if not escalation_channel:
            return

        escalation_channel.sudo().message_post(
            body=(
                f"<b>Escalación WhatsApp</b><br/>"
                f"Cliente: {partner_info}<br/>"
                f"Motivo: {reason}<br/>"
                f"Canal: <a href='/web#model=discuss.channel&amp;id={self.id}'>Ver conversación</a>"
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

    # ------------------------------------------------------------------
    # Tool execution (partner-isolated)
    # ------------------------------------------------------------------

    def _execute_wa_tool(self, tool_name, tool_input, session):
        tools = self.env['insotech.mcp.tools'].sudo()
        partner_id = session.partner_id.id
        safe_input = dict(tool_input or {})

        # Tools that always receive partner_id injected
        _partner_inject = {
            'list_invoices', 'get_outstanding_balance',
            'list_orders', 'get_active_orders',
        }
        # Tools that receive partner_id for access check
        _partner_check = {
            'get_invoice', 'get_order', 'get_payment_link',
            'send_invoice_email', 'add_line_to_order',
        }
        # Tools that receive partner_id as the order owner
        _partner_owner = {'create_confirmed_order'}

        if tool_name in _partner_inject:
            safe_input['partner_id'] = partner_id
        elif tool_name in _partner_check:
            safe_input['partner_id'] = partner_id
        elif tool_name in _partner_owner:
            safe_input['partner_id'] = partner_id

        method_name = f'tool_{tool_name}'
        if not hasattr(tools, method_name):
            return {'error': f'Herramienta {tool_name} no disponible.'}

        try:
            return getattr(tools, method_name)(**safe_input)
        except Exception as e:
            _logger.error("WA Assistant tool %s error: %s", tool_name, e)
            return {'error': str(e)}

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _bot_reply(self, text):
        self.sudo().message_post(
            body=text,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

    def _get_welcome_msg(self):
        ICP = self.env['ir.config_parameter'].sudo()
        bot_name = ICP.get_param('insotech_wa_assistant.bot_name', 'Asistente')
        return (
            f"Hola! Soy {bot_name}.\n\n"
            "Para consultar tus facturas, pedidos o hacer un nuevo pedido, "
            "necesito verificar tu identidad.\n\n"
            "Por favor escribe tu NIT (sin digito de verificacion):"
        )

    def _compute_dv_safe(self, nit_base):
        try:
            from odoo.addons.insotech_core.utils.dian import compute_dv
            return compute_dv(nit_base)
        except Exception:
            return ''
