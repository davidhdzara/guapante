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

        self._signup_with_values(qcontext.get('token'), values)
        request.env.cr.commit()
