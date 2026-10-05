# -*- coding: utf-8 -*-
"""Evidencia inmutable de intercambios SOAP de Nómina Electrónica."""

import base64
import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class L10nCoNeExchange(models.Model):
    _name = 'l10n.co.ne.exchange'
    _description = 'Intercambio DIAN de Nómina Electrónica'
    _order = 'create_date desc, id desc'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 readonly=True, ondelete='restrict')
    operation = fields.Selection([
        ('send_sync', 'Envío síncrono'),
        ('send_test_set', 'Envío set de pruebas'),
        ('get_status_zip', 'Consulta de estado'),
    ], required=True, readonly=True)
    endpoint = fields.Char(required=True, readonly=True)
    zip_key = fields.Char(readonly=True, index=True)
    queried_zip_key = fields.Char(readonly=True, index=True)
    parent_exchange_id = fields.Many2one('l10n.co.ne.exchange', readonly=True,
        ondelete='restrict')
    transport_error = fields.Text(readonly=True)
    request_payload = fields.Binary(attachment=True, readonly=True)
    response_payload = fields.Binary(attachment=True, readonly=True)
    payslip_ids = fields.Many2many('hr.payslip',
        'l10n_co_ne_exchange_payslip_rel', 'exchange_id', 'payslip_id',
        string='Nóminas', readonly=True)
    document_ids = fields.One2many('l10n.co.ne.exchange.document', 'exchange_id',
        string='Manifiesto', readonly=True)
    unidentified_count = fields.Integer(
        string='Resultados sin identificar', readonly=True, default=0,
        help='Cantidad de DianResponse de esta consulta que no traían '
             'ningún identificador utilizable (CUNE/XmlDocumentKey/'
             'referencia UBL) y cuyo manifiesto tenía más de 1 documento '
             '-- no se les pudo asociar un payslip, por lo que no '
             'cambiaron de estado. Requieren conciliación manual.',
    )

    def write(self, vals):
        raise AccessError(_('El historial DIAN es evidencia inmutable.'))

    def unlink(self):
        raise AccessError(_('El historial DIAN no puede eliminarse automáticamente.'))

    @staticmethod
    def _binary(value):
        if not value:
            return False
        if isinstance(value, str):
            value = value.encode('utf-8')
        return base64.b64encode(value)

    def create_exchange(self, company, operation, endpoint, response, payslips,
                        manifest=None, queried_zip_key=None, parent_exchange=None,
                        unidentified_count=0):
        """Crea evidencia completa sin registrar payloads en el log."""
        request = response.get('RawRequest', b'')
        answer = response.get('RawResponse', b'')
        if any(payslip.company_id != company for payslip in payslips):
            raise AccessError(_('Una evidencia DIAN no puede mezclar compañías.'))
        record = self.sudo().create({
            'company_id': company.id,
            'operation': operation,
            'endpoint': endpoint,
            'zip_key': response.get('ZipKey') or False,
            'queried_zip_key': queried_zip_key or False,
            'parent_exchange_id': parent_exchange.id if parent_exchange else False,
            'transport_error': response.get('TransportError') or (
                response.get('ErrorMessage') if response.get('StatusCode') == 'CONNECTION_ERROR' else False),
            'request_payload': self._binary(request),
            'response_payload': self._binary(answer),
            'payslip_ids': [(6, 0, payslips.ids)],
            'unidentified_count': unidentified_count,
        })
        for item in manifest or []:
            xml = item['xml']
            self.env['l10n.co.ne.exchange.document'].sudo().create({
                'exchange_id': record.id,
                'payslip_id': item['payslip'].id,
                'cune': item['payslip'].l10n_co_ne_cune,
                'file_name': item['filename'],
                'sha256': hashlib.sha256(xml).hexdigest(),
                'signed_xml': self._binary(xml),
                'manifest_json': json.dumps({
                    'payslip_id': item['payslip'].id,
                    'cune': item['payslip'].l10n_co_ne_cune,
                    'file_name': item['filename'],
                    'sha256': hashlib.sha256(xml).hexdigest(),
                }, sort_keys=True),
            })
        return record


class L10nCoNeExchangeDocument(models.Model):
    _name = 'l10n.co.ne.exchange.document'
    _description = 'Documento del manifiesto DIAN'
    _order = 'id'

    exchange_id = fields.Many2one('l10n.co.ne.exchange', required=True,
        readonly=True, ondelete='cascade')
    company_id = fields.Many2one(related='exchange_id.company_id', store=True,
        readonly=True, index=True)
    payslip_id = fields.Many2one('hr.payslip', required=True, readonly=True,
        ondelete='restrict')
    cune = fields.Char(readonly=True, index=True)
    file_name = fields.Char(required=True, readonly=True)
    sha256 = fields.Char(required=True, readonly=True)
    signed_xml = fields.Binary(attachment=True, readonly=True)
    manifest_json = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.company_id != record.payslip_id.company_id:
                raise AccessError(_('El manifiesto no puede cruzar compañías.'))
        return records

    def write(self, vals):
        raise AccessError(_('El manifiesto DIAN es evidencia inmutable.'))

    def unlink(self):
        raise AccessError(_('El manifiesto DIAN no puede eliminarse automáticamente.'))
