# -*- coding: utf-8 -*-
import datetime
import logging
from werkzeug.exceptions import Forbidden

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class RadianPortalController(http.Controller):
    """Controller to handle RADIAN event triggers from the Customer Portal."""

    @http.route(
        ['/my/invoices/<int:invoice_id>/radian/<string:event_code>'],
        type='http', auth="public", website=True, methods=['POST']
    )
    def trigger_radian_event(self, invoice_id, event_code, access_token=None, **post):
        """Handle RADIAN event generation (030, 032, 033, 034) from portal."""
        from urllib.parse import urlencode
        
        def _redirect_msg(invoice, msg_type, message):
            url = invoice.get_portal_url()
            qs = urlencode({msg_type: str(message)})
            return request.redirect(f"{url}&{qs}" if "?" in url else f"{url}?{qs}")
        
        # 1. Access Validation (Odoo core check)
        try:
            invoice_sudo = self._document_check_access('account.move', invoice_id, access_token)
        except Forbidden:
            _logger.warning("Insotech RADIAN Portal: Forbidden access to invoice %s", invoice_id)
            return request.redirect('/my')

        # 2. Check Mandate (Checkbox required=True in UI, double-check in backend)
        mandate_accepted = post.get('mandate_accepted') == '1'
        if not mandate_accepted:
            # Mandate not accepted, redirect back with error
            return _redirect_msg(invoice_sudo, 'radian_error', _('Debe aceptar el mandato legal para continuar.'))

        # 3. Validation: Invoice state must be 'accepted' by DIAN
        if not invoice_sudo.insotech_dian_status == 'accepted':
            return _redirect_msg(invoice_sudo, 'radian_error', _('La factura no ha sido aceptada por la DIAN todavía.'))

        # 4. Create RADIAN Event
        valid_codes = ['030', '031', '032', '033', '034']
        if event_code not in valid_codes:
            return _redirect_msg(invoice_sudo, 'radian_error', _('Código de evento RADIAN inválido.'))

        client_ip = request.httprequest.remote_addr
        now = datetime.datetime.now()

        # Check existing events to prevent duplicates
        existing = request.env['insotech.radian.event'].sudo().search([
            ('move_id', '=', invoice_sudo.id),
            ('event_code', '=', event_code),
            ('state', '!=', 'error')
        ])

        if existing:
            return _redirect_msg(invoice_sudo, 'radian_warning', _('Este evento ya fue registrado previamente.'))

        # Create record capturing Forensic Evidence
        try:
            event = request.env['insotech.radian.event'].sudo().create({
                'move_id': invoice_sudo.id,
                'company_id': invoice_sudo.company_id.id,
                'event_code': event_code,
                'source': 'portal',
                'state': 'done',
                'mandate_ip': client_ip,
                'mandate_timestamp': now,
                'notes': "Mandato explícito aceptado por el usuario en el Portal B2B.",
                'claim_code': post.get('claim_code') if event_code == '034' else False,
            })
            
            # Post a message on chatter for internal traceability
            invoice_sudo.message_post(
                body=f"<b>Evento RADIAN ({event_code})</b> solicitado desde el portal por IP: {client_ip}.",
                message_type='comment',
            )
            
            # TRIGGER SOAP TRANSMISSION IMMEDIATELY
            event.sudo().action_send_to_dian()
            
            if event.state == 'error':
                safe_err_msg = str(event.notes)[:250] + "..." if event.notes and len(str(event.notes)) > 250 else str(event.notes)
                return _redirect_msg(invoice_sudo, 'radian_error', _(f'Transmisión fallida: {safe_err_msg}'))
            
            return _redirect_msg(invoice_sudo, 'radian_success', _(f'Evento {event_code} transmitido con éxito (Código Validación DIAN: {str(event.notes)[:50] if event.notes else "OK"}).'))

        except Exception as e:
            _logger.error("Insotech RADIAN Portal: Error creating event %s: %s", event_code, str(e))
            return _redirect_msg(invoice_sudo, 'radian_error', _('Ocurrió un error registrando el evento RADIAN.'))

    def _document_check_access(self, model_name, document_id, access_token=None):
        """Helper to check access rights using core Odoo mechanism."""
        document = request.env[model_name].browse([document_id])
        document_sudo = document.sudo().with_context(active_test=False)
        if not document_sudo.exists():
            raise Forbidden()
        try:
            document.check_access_rights('read')
            document.check_access_rule('read')
        except Exception:
            if not access_token or not document_sudo.access_token:
                raise Forbidden()
            from odoo.tools import consteq
            if not consteq(document_sudo.access_token, access_token):
                raise Forbidden()
        return document_sudo
