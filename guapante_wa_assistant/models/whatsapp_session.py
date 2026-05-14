# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models


class GuapanteWaSession(models.Model):
    _name = 'guapante.wa.session'
    _description = 'Sesión del Asistente WhatsApp'
    _order = 'last_activity desc'

    whatsapp_number = fields.Char(
        string='Número WhatsApp',
        required=True,
        index=True,
    )
    channel_id = fields.Many2one(
        'discuss.channel',
        string='Canal de Conversación',
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente Autenticado',
        ondelete='set null',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ('pending_nit', 'Esperando NIT'),
            ('pending_branch', 'Esperando Selección de Sucursal'),
            ('pending_confirm', 'Esperando Confirmación de Número'),
            ('authenticated', 'Autenticado'),
            ('needs_human', 'Requiere Asesor'),
            ('blocked', 'Bloqueado'),
            ('expired', 'Expirado'),
        ],
        string='Estado',
        default='pending_nit',
        required=True,
        index=True,
    )
    # JSON list: [{"id": int, "name": str, "street": str, "city": str}, ...]
    pending_options = fields.Text(string='Opciones Pendientes (JSON)')
    nit_attempt = fields.Char(string='NIT Intentado')
    nit_tries = fields.Integer(string='Intentos de NIT', default=0)
    escalation_reason = fields.Text(string='Motivo de Escalación')
    conversation_history = fields.Text(
        string='Historial de Conversación (JSON)',
        default='[]',
    )
    last_activity = fields.Datetime(
        string='Última Actividad',
        default=fields.Datetime.now,
    )
    message_count = fields.Integer(string='Mensajes en Sesión', default=0)

    @api.model
    def _get_or_create_session(self, whatsapp_number, channel_id=None):
        """Return an active non-expired session or create a fresh one."""
        ttl_minutes = int(
            self.env['ir.config_parameter']
            .sudo()
            .get_param('guapante_wa_assistant.session_ttl_minutes', '30')
        )
        expiry_threshold = fields.Datetime.now() - timedelta(minutes=ttl_minutes)

        session = self.sudo().search(
            [
                ('whatsapp_number', '=', whatsapp_number),
                ('state', 'not in', ['expired', 'blocked']),
                ('last_activity', '>', expiry_threshold),
            ],
            limit=1,
            order='last_activity desc',
        )
        if session:
            session.sudo().write({'last_activity': fields.Datetime.now()})
            return session

        vals = {
            'whatsapp_number': whatsapp_number,
            'state': 'pending_nit',
            'conversation_history': '[]',
        }
        if channel_id:
            vals['channel_id'] = channel_id
        return self.sudo().create(vals)

    def reset(self):
        """Reset session to initial state."""
        self.ensure_one()
        self.sudo().write({
            'state': 'pending_nit',
            'partner_id': False,
            'nit_attempt': False,
            'nit_tries': 0,
            'pending_options': False,
            'escalation_reason': False,
            'conversation_history': '[]',
        })

    def action_release_to_bot(self):
        """Return session to authenticated state so the bot resumes."""
        self.ensure_one()
        self.sudo().write({
            'state': 'authenticated',
            'escalation_reason': False,
        })
        return True
