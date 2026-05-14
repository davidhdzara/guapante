# -*- coding: utf-8 -*-
from odoo import api, fields, models

_PARAM = 'guapante_wa_assistant.'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- Bot identity ---
    wa_bot_name = fields.Char(
        string='Nombre del Asistente',
        config_parameter=_PARAM + 'bot_name',
        help='Nombre con el que el bot se presenta al cliente. Ej: Sofía, Asistente, etc.',
    )
    wa_company_description = fields.Char(
        string='Descripción de la Empresa (para el bot)',
        config_parameter=_PARAM + 'company_description',
        help=(
            'Frase corta que describe la empresa. El bot la usa en su presentación. '
            'Ej: "empresa colombiana de frutas y verduras"'
        ),
    )

    # --- API / model ---
    wa_anthropic_api_key = fields.Char(
        string='API Key de Anthropic',
        config_parameter=_PARAM + 'anthropic_api_key',
    )
    wa_claude_model = fields.Char(
        string='Modelo de Claude',
        config_parameter=_PARAM + 'claude_model',
    )

    # --- Session ---
    wa_session_ttl_minutes = fields.Integer(
        string='Duración de Sesión (minutos)',
        config_parameter=_PARAM + 'session_ttl_minutes',
    )

    # --- Escalation ---
    wa_escalation_channel_id = fields.Many2one(
        'discuss.channel',
        string='Canal de Escalación',
        compute='_compute_wa_escalation_channel',
        inverse='_set_wa_escalation_channel',
        help='Canal de Discuss donde se notifica cuando un cliente solicita un asesor.',
    )

    def _compute_wa_escalation_channel(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for rec in self:
            channel_id = int(ICP.get_param(_PARAM + 'escalation_channel_id', '0') or 0)
            rec.wa_escalation_channel_id = (
                self.env['discuss.channel'].browse(channel_id)
                if channel_id
                else False
            )

    def _set_wa_escalation_channel(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for rec in self:
            ICP.set_param(
                _PARAM + 'escalation_channel_id',
                str(rec.wa_escalation_channel_id.id) if rec.wa_escalation_channel_id else '0',
            )
