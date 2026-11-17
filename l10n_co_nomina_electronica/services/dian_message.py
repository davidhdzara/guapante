# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Motivo de aceptación o rechazo de un envío a la DIAN (doc 53 §16.5).

Funciones puras (sin Odoo): ``build_message_json`` toma lo que ya devuelve
``soap_client._parse_response`` (sin parsing nuevo de SOAP) y ``render_message_html`` arma el
texto del popover. La respuesta de la DIAN es entrada NO confiable: todo se escapa."""

import html

_TRANSPORT_CODES = ('CONNECTION_ERROR', 'PARSE_ERROR', 'ERROR')


def build_message_json(parsed):
    """Json del intento: {'is_valid', 'status_code', 'status', 'detail', 'errors', 'transport', 'fault'}."""
    parsed = parsed or {}
    status_code = parsed.get('StatusCode') or ''
    transport = False
    if status_code in _TRANSPORT_CODES:
        transport = status_code
    elif parsed.get('HttpStatus') and str(parsed['HttpStatus']) != '200':
        transport = 'HTTP %s' % parsed['HttpStatus']
    errors = list(parsed.get('ErrorMessages') or [])
    if not errors and parsed.get('ErrorMessage'):
        errors = [parsed['ErrorMessage']]
    return {
        'is_valid': str(parsed.get('IsValid') or '').strip().lower() == 'true',
        'status_code': status_code,
        'status': parsed.get('StatusDescription') or '',
        'detail': parsed.get('StatusMessage') or '',
        'errors': errors,
        'transport': transport,
        'fault': list(parsed.get('FaultDetails') or []) if parsed.get('SOAPFault') else [],
    }


def render_message_html(message_json, translate=lambda texto: texto):
    """HTML (texto ya escapado) del motivo. ``translate`` recibe los textos propios (no los de la DIAN)."""
    mj = message_json or {}
    esc = html.escape
    partes = []
    if mj.get('transport'):
        partes.append('<p>%s: %s</p>' % (
            esc(translate('El servidor de la DIAN no respondió')),
            esc(' '.join([mj['transport']] + list(mj.get('errors') or [])))))
    elif mj.get('fault'):
        partes.append('<p>%s: %s</p>' % (
            esc(translate('Error del servicio de la DIAN')), esc(' '.join(mj['fault']))))
    else:
        if mj.get('status'):
            partes.append('<p>%s</p>' % esc(mj['status']))
        if mj.get('detail'):
            partes.append('<p>%s</p>' % esc(mj['detail']))
        if mj.get('errors'):
            partes.append('<ul>%s</ul>' % ''.join('<li>%s</li>' % esc(e) for e in mj['errors']))
        elif not mj.get('status_code') and not mj.get('is_valid'):
            partes.append('<p>%s</p>' % esc(translate('Consulte de nuevo en unos minutos.')))
    return ''.join(partes)
