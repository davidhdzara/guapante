# -*- coding: utf-8 -*-
import hashlib
import secrets
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class GuapanteMcpApiKey(models.Model):
    _name = 'guapante.mcp.api.key'
    _description = 'Guapante MCP API Key'
    _order = 'create_date desc'

    name = fields.Char(string='Nombre / Cliente', required=True)
    token_hash = fields.Char(string='Token (Hash SHA-256)', readonly=True, copy=False, index=True)
    token_prefix = fields.Char(string='Prefijo Visible', readonly=True, copy=False)
    scope = fields.Selection(
        [('admin', 'Administrador'), ('user', 'Usuario Final')],
        string='Alcance',
        required=True,
        default='user',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner (requerido para Usuario Final)',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
    )
    expiry_date = fields.Date(string='Fecha de Expiración')
    active = fields.Boolean(default=True)
    last_used = fields.Datetime(string='Último Uso', readonly=True, copy=False)
    request_count = fields.Integer(
        string='Total Solicitudes',
        readonly=True,
        copy=False,
        default=0,
    )
    notes = fields.Text(string='Notas')

    @api.constrains('scope', 'partner_id')
    def _check_user_scope_partner(self):
        for rec in self:
            if rec.scope == 'user' and not rec.partner_id:
                raise UserError(
                    _('El alcance "Usuario Final" requiere un partner asignado.')
                )

    def action_generate_token(self):
        """Generate a new token, store its hash and return the raw token once."""
        self.ensure_one()
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        self.write({
            'token_hash': token_hash,
            'token_prefix': raw_token[:8],
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Token Generado — Cópialo Ahora'),
                'message': _(
                    'Este token NO se mostrará de nuevo. Cópialo y guárdalo:\n\n%s'
                ) % raw_token,
                'type': 'warning',
                'sticky': True,
            },
        }

    def action_revoke_token(self):
        """Revoke the current token by clearing its hash."""
        self.ensure_one()
        self.write({'token_hash': False, 'token_prefix': False})

    @api.model
    def _validate_token(self, raw_token):
        """Return the API key record if the token is valid, else None."""
        if not raw_token:
            return None
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        key = self.sudo().search(
            [('token_hash', '=', token_hash), ('active', '=', True)],
            limit=1,
        )
        if not key:
            return None
        if key.expiry_date and key.expiry_date < date.today():
            return None
        key.sudo().write({
            'last_used': fields.Datetime.now(),
            'request_count': key.request_count + 1,
        })
        return key
