# -*- coding: utf-8 -*-
import logging
from odoo import http, _, models
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class GuapanteAuthSignupHome(AuthSignupHome):

    def get_auth_signup_qcontext(self):
        """ Add identification types to the signup context for the dropdown. """
        qcontext = super().get_auth_signup_qcontext()
        # Fetch identification types for Colombia
        country_co = request.env.ref('base.co', raise_if_not_found=False)
        domain = [('country_id', '=', country_co.id)] if country_co else []
        
        qcontext['identification_types'] = request.env['l10n_latam.identification.type'].sudo().search(domain)
        
        # LOGGING IDENTIFICATION TYPES TO VERIFY AVAILABILITY
        type_names = [t.name for t in qcontext['identification_types']]
        _logger.info("🔎 Guapante Signup - Available ID Types: %s", type_names)
        
        return qcontext

    def do_signup(self, qcontext):
        """ Override to handle custom fields and duplication check. """
        values = {key: qcontext.get(key) for key in ('login', 'name', 'password', 'company_type', 'vat', 'l10n_latam_identification_type_id')}
        
        # LOGGING FOR DEBUG
        _logger.info("🔵 Guapante Signup - Values Received: %s", values)

        # Cast Many2one to int if present
        if values.get('l10n_latam_identification_type_id'):
            try:
                values['l10n_latam_identification_type_id'] = int(values['l10n_latam_identification_type_id'])
            except ValueError:
                values.pop('l10n_latam_identification_type_id')

        # --- Validation Logic ---
        email = values.get('login')
        vat = values.get('vat')
        
        if not values.get('name'):
            raise UserError(_("The name is required."))
        
        if not email:
            raise UserError(_("The email is required."))

        Partner = request.env['res.partner'].sudo()
        
        # 1. Check duplicate Email
        if Partner.search_count([('email', '=', email)]) > 0:
             raise UserError(_("Another user is already registered using this email address."))

        # 2. Check duplicate VAT (if provided)
        if vat:
            if Partner.search_count([('vat', '=', vat)]) > 0:
                raise UserError(_("A partner with this Tax ID (NIT) already exists."))

        # Password confirmation check
        if values.get('password') != qcontext.get('confirm_password'):
            raise UserError(_("Passwords do not match; please retype them."))

        # Language support
        supported_lang_codes = [code for code, _ in request.env['res.lang'].get_installed()]
        lang = request.context.get('lang', '')
        if lang in supported_lang_codes:
            values['lang'] = lang

        # Store custom values in context for _signup_create_user to access
        request.env.context = dict(request.env.context, 
            signup_company_type=values.get('company_type'),
            signup_vat=values.get('vat'),
            signup_identification_type_id=values.get('l10n_latam_identification_type_id')
        )

        # Call parent signup
        self._signup_with_values(qcontext.get('token'), values)
        request.env.cr.commit()

    def _signup_create_user(self, values):
        """ Override to inject custom partner fields during user creation. """
        _logger.info("🟢 Guapante Signup - Creating User with values: %s", values)
        
        # Get custom values from context
        company_type = request.env.context.get('signup_company_type', 'person')
        vat = request.env.context.get('signup_vat')
        identification_type_id = request.env.context.get('signup_identification_type_id')
        
        # Create user using parent method
        user_sudo = super()._signup_create_user(values)
        
        # Immediately update the partner with custom fields
        partner_values = {
            'company_type': company_type,
        }
        
        if vat:
            partner_values['vat'] = vat
            
        if identification_type_id:
            partner_values['l10n_latam_identification_type_id'] = identification_type_id
        
        _logger.info("🟡 Guapante Signup - Updating Partner %s with: %s", user_sudo.partner_id.id, partner_values)
        user_sudo.partner_id.write(partner_values)
        
        _logger.info("🟢 Guapante Signup - Partner Updated Successfully!")
        return user_sudo
