# -*- coding: utf-8 -*-
import logging
from odoo import http, _, models
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import UserError
import werkzeug
import uuid

_logger = logging.getLogger(__name__)

class GuapanteAuthSignupHome(AuthSignupHome):

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()
        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                self.do_signup(qcontext)
                
                # Enviar correo de verificación (Reset Password)
                user = request.env['res.users'].sudo().search([('login', '=', qcontext.get('login'))], limit=1)
                if user:
                    user.action_reset_password()
                
                # Renderizar éxito en lugar de autologuear
                qcontext['successful_signup'] = True
                response = request.render('auth_signup.signup', qcontext)
                response.headers['X-Frame-Options'] = 'SAMEORIGIN'
                response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
                return response

            except UserError as e:
                qcontext['error'] = e.args[0]
            except (Exception) as e:
                if request.env["res.users"].sudo().search([("login", "=", qcontext.get("login"))]):
                    qcontext["error"] = _("Another user is already registered using this email address.")
                else:
                    _logger.error("%s", e)
                    qcontext['error'] = _("Could not create a new account.")

        response = request.render('auth_signup.signup', qcontext)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

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
        identification_type_id = values.get('l10n_latam_identification_type_id')
        company_type = values.get('company_type')
        
        if not values.get('name'):
            raise UserError(_("The name is required."))
        
        if not email:
            raise UserError(_("The email is required."))

        if not vat:
            raise UserError(_("El Número de Documento es obligatorio."))

        if not identification_type_id:
            raise UserError(_("El Tipo de Identificación es obligatorio."))

        # Integrity check: If Company, it MUST be NIT.
        if company_type == 'company':
            id_type_record = request.env['l10n_latam.identification.type'].sudo().browse(identification_type_id)
            if id_type_record.exists() and 'NIT' not in id_type_record.name.upper():
                raise UserError(_("Una Empresa debe registrarse con NIT."))

        Partner = request.env['res.partner'].sudo()
        
        # 1. Check duplicate Email
        if Partner.search_count([('email', '=', email)]) > 0:
             raise UserError(_("Another user is already registered using this email address."))

        # Check duplicate VAT (if provided)
        if vat:
            if Partner.search_count([('vat', '=', vat)]) > 0:
                raise UserError(_("A partner with this Tax ID (NIT) already exists."))

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

        # Generate random password for deferred password flow
        token = qcontext.get('token')
        values['password'] = str(uuid.uuid4())

        # Call model signup directly without authenticating the session
        request.env['res.users'].sudo().signup(values, token)
        request.env.cr.commit()


