# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.
"""Intento de envío de un documento mensual a la DIAN (doc 53 §16.2, §18.2): calco de ``l10n_co_dian.document``.

Es el resumen MUTABLE de un envío (cambia de estado al consultar); la evidencia cruda inmutable sigue en
``l10n.co.ne.exchange``."""

from markupsafe import Markup

from odoo import _, api, fields, models

from ..services import dian_message, dian_respuesta


class L10nCoNeDocumentoIntento(models.Model):
    _name = 'l10n.co.ne.documento.intento'
    _description = 'Intento de envío del documento mensual a la DIAN'
    _order = 'datetime desc, id desc'
    _check_company_auto = True

    documento_id = fields.Many2one('l10n.co.ne.documento', string='Documento', required=True,
                                   ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one('res.company', related='documento_id.company_id', store=True,
                                 index=True, readonly=True)
    datetime = fields.Datetime(string='Fecha y hora', help='Momento del envío (UTC en base de datos; se muestra en la zona del usuario).')
    state = fields.Selection([
        ('invoice_sending_failed', 'Envío fallido'),
        ('invoice_pending', 'Pendiente'),
        ('invoice_rejected', 'Rechazado'),
        ('invoice_accepted', 'Aceptado'),
    ], string='Estado DIAN', required=True, copy=False,
        help='Estado de ESTE envío; se actualiza al consultar. Mismas claves que el estado nativo de la factura electrónica.')
    identifier = fields.Char(string='CUNE', copy=False, index=True)
    zip_key = fields.Char(string='ZipKey', copy=False)
    numero = fields.Char(string='Número', copy=False, help='Consecutivo usado en este envío (cada intento conserva el suyo).')
    file_name = fields.Char(string='Archivo', copy=False)
    sha256 = fields.Char(string='SHA-256', copy=False)
    attachment_id = fields.Many2one('ir.attachment', string='Adjunto', copy=False, ondelete='set null')
    message_json = fields.Json(string='Respuesta DIAN (datos)', copy=False)
    respuesta_attachment_id = fields.Many2one(
        'ir.attachment', string='Respuesta DIAN (XML)', copy=False, ondelete='set null',
        help='ApplicationResponse de la DIAN decodificado (constancia de aceptado o rechazado con la regla y el mensaje): evidencia '
             'legible. El sobre SOAP completo sigue guardado, inmutable, en la evidencia (intercambio) DIAN.')
    message = fields.Html(string='Motivo', compute='_compute_message', sanitize=False)
    test_environment = fields.Boolean(string='Ambiente de pruebas')
    certification_process = fields.Boolean(string='Proceso de habilitación')
    exchange_id = fields.Many2one('l10n.co.ne.exchange', string='Evidencia DIAN', copy=False,
                                  ondelete='set null', check_company=True)
    ya_procesado = fields.Boolean(
        string='Respondió «procesado anteriormente»', copy=False, readonly=True,
        help='La DIAN contestó la regla 90 a este envío. Un número que la recibió no se vuelve a usar.')
    show_button_get_status = fields.Boolean(compute='_compute_show_button_get_status')

    def _ne_recibio_regla_90(self):
        """True si la DIAN contestó la regla 90 a este envío: la marca del envío o, en uno anterior a .337, la respuesta guardada."""
        self.ensure_one()
        datos = self.message_json or {}
        return self.ya_procesado or dian_respuesta.es_ya_procesado({'StatusCode': datos.get('status_code'), 'ErrorMessages': datos.get('errors')})

    @api.depends('message_json')
    def _compute_message(self):
        for intento in self:
            texto = dian_message.render_message_html(intento.message_json, translate=_)
            intento.message = Markup(texto) if texto else False

    @api.depends('state', 'zip_key')
    def _compute_show_button_get_status(self):
        for intento in self:
            intento.show_button_get_status = bool(intento.zip_key) and intento.state in (
                'invoice_pending', 'invoice_sending_failed')

    def _ne_guardar_application_response(self, respuesta):
        """E-1 (doc 59 §18.11-18.12): adjunta al intento el ``ApplicationResponse`` de la DIAN YA DECODIFICADO como archivo ``.xml``
        (``ApplicationResponse_<consecutivo>_<n° de intento>.xml``). El sobre completo ya queda guardado e inmutable en el
        intercambio; esto lo hace legible para un contador o un auditor (aceptado/rechazado, regla, mensaje, CUNE). Sin
        ``ApplicationResponse`` en la respuesta no se crea nada. Una reconsulta con otro contenido deja un adjunto nuevo y el campo
        apunta al ultimo (los anteriores siguen adjuntos al intento)."""
        self.ensure_one()
        respuesta = respuesta or {}
        texto = respuesta.get('ApplicationResponse') or next(
            (r.get('ApplicationResponse') for r in respuesta.get('DianResponses') or [] if r.get('ApplicationResponse')), '')
        if not texto:
            return self.env['ir.attachment']
        contenido = texto.encode('utf-8') if isinstance(texto, str) else texto
        actual = self.respuesta_attachment_id
        if actual and actual.raw == contenido:
            return actual
        adjunto = self.env['ir.attachment'].sudo().create({
            'name': 'ApplicationResponse_%s_%s.xml' % (self.numero or self.documento_id.consecutive or self.id, self.id),
            'raw': contenido, 'mimetype': 'application/xml', 'res_model': self._name, 'res_id': self.id})
        self.sudo().respuesta_attachment_id = adjunto
        return adjunto
