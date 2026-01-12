# -*- coding: utf-8 -*-
import logging
from odoo import http, _
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class GuapanteAuthSignupHome(AuthSignupHome):

    def get_auth_signup_qcontext(self):
        """ Add identification types to the signup context for the dropdown. """
        qcontext = super().get_auth_signup_qcontext()
        # Fetch identification types for Colombia (or general if filter not needed yet)
        # We try to filter by current company country, or fallback to all
        country_co = request.env.ref('base.co', raise_if_not_found=False)
        domain = [('country_id', '=', country_co.id)] if country_co else []
        
        qcontext['identification_types'] = request.env['l10n_latam.identification.type'].sudo().search(domain)
        return qcontext

    def do_signup(self, qcontext):
        """ Override to handle custom fields and duplication check. """
        values = {key: qcontext.get(key) for key in ('login', 'name', 'password', 'company_type', 'vat', 'l10n_latam_identification_type_id')}
        
        # LOGGING FOR DEBUG
        _logger.info("Guapante Signup Values Received: %s", values)

        # Cast Many2one to int if present
        if values.get('l10n_latam_identification_type_id'):
            try:
                values['l10n_latam_identification_type_id'] = int(values['l10n_latam_identification_type_id'])
            except ValueError:
                values.pop('l10n_latam_identification_type_id') # Remove if invalid

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

        # Update values for signup
        # 'signup' method in res.users expects keys that match res.users/res.partner fields
        # company_type is 'person' or 'company'
        
        # We need to make sure we call super logic but passing our extended values
        # The standard do_signup re-extracts values from qcontext.
        # So we update qcontext (which is mutable) or we explicitly call signup here.
        
        # Standard Odoo AuthSignupHome.do_signup implementation:
        # values = { key: qcontext.get(key) for key in ('login', 'name', 'password') }
        # if not values: raise UserError(_("The form was not properly filled in."))
        # if values.get('password') != qcontext.get('confirm_password'): raise UserError(_("Passwords do not match; please retype them."))
        # supported_lang_codes = [code for code, _ in request.env['res.lang'].get_installed()]
        # lang = request.context.get('lang', '')
        # if lang in supported_lang_codes: values['lang'] = lang
        # self._signup_with_values(qcontext.get('token'), values)
        # request.env.cr.commit()

        # So to inject our fields, we just need to ensure `_signup_with_values` receives them.
        # BUT `do_signup` filters the dict it passes to `_signup_with_values`.
        
        # Strategy: We copy-paste the standard implementation but expand the dictionary list.
        # This is safer than monkey-patching or relying on super() if super filters keys.

        if values.get('password') != qcontext.get('confirm_password'):
            raise UserError(_("Passwords do not match; please retype them."))

        supported_lang_codes = [code for code, _ in request.env['res.lang'].get_installed()]
        lang = request.context.get('lang', '')
        if lang in supported_lang_codes:
            values['lang'] = lang

        # Create the user using standard logic
        self._signup_with_values(qcontext.get('token'), values)
        
        # --- EXPLICIT DATA PERSISTENCE FIX ---
        # Fetch the newly created user and update the partner fields explicitly
        # This ensures 'company_type' and 'vat' are saved even if standard signup ignored them
        request.env.cr.commit() # Commit to ensure user exists
        
        user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if user:
            partner_values = {
                'company_type': values.get('company_type'),
                'vat': values.get('vat'),
            }
            # Only add identification type if valid int
            if values.get('l10n_latam_identification_type_id'):
                partner_values['l10n_latam_identification_type_id'] = values.get('l10n_latam_identification_type_id')
                
            user.partner_id.sudo().write(partner_values)
            _logger.info("Guapante Signup: Updated Partner %s with %s", user.partner_id.id, partner_values)

        # Final commit
        request.env.cr.commit()
