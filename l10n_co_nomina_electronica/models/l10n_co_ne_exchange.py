# -*- coding: utf-8 -*-
"""Evidencia inmutable de intercambios SOAP de Nómina Electrónica."""

import base64
import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class L10nCoNeExchange(models.Model):
    _name = 'l10n.co.ne.exchange'
    _check_company_auto = True      # H-F2-03 (C5): la compañía de los recibos y del intercambio anterior es la del intercambio
    _description = 'Intercambio DIAN de Nómina Electrónica'
    _order = 'create_date desc, id desc'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 readonly=True, ondelete='restrict')
    operation = fields.Selection([
        ('send_sync', 'Envío síncrono'),
        ('send_test_set', 'Envío set de pruebas'),
        ('get_status_zip', 'Consulta de estado'),
        ('get_status', 'Consulta de estado por CUNE'),
    ], required=True, readonly=True)
    endpoint = fields.Char(required=True, readonly=True)
    zip_key = fields.Char(readonly=True, index=True)
    queried_zip_key = fields.Char(readonly=True, index=True)
    parent_exchange_id = fields.Many2one('l10n.co.ne.exchange', readonly=True,
        ondelete='restrict', check_company=True)
    transport_error = fields.Text(readonly=True)
    request_payload = fields.Binary(attachment=True, readonly=True)
    response_payload = fields.Binary(attachment=True, readonly=True)
    request_filename = fields.Char(compute='_compute_nombres_descarga', string='Archivo de la solicitud')
    response_filename = fields.Char(compute='_compute_nombres_descarga', string='Archivo de la respuesta')
    payslip_ids = fields.Many2many('hr.payslip',
        'l10n_co_ne_exchange_payslip_rel', 'exchange_id', 'payslip_id',
        string='Nóminas', readonly=True, check_company=True)
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

    @api.depends('zip_key', 'queried_zip_key')
    def _compute_nombres_descarga(self):
        """Nombre con el que se DESCARGAN la solicitud y la respuesta SOAP (E-1, pieza ``.xml``): los payloads son XML y el
        nombre era el ``zip_key`` a secas, sin extension y igual para los dos archivos. Base: el ZipKey del envio o, en una
        consulta, el consultado; una consulta por CUNE no trae ninguno y usa el id del intercambio."""
        for record in self:
            base = record.zip_key or record.queried_zip_key or 'intercambio_%s' % record.id
            record.request_filename = '%s_solicitud.xml' % base
            record.response_filename = '%s_respuesta.xml' % base

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
                        unidentified_count=0, *, documento=None):
        """Crea evidencia completa sin registrar payloads en el log.

        ``documento`` (solo por nombre, doc 53 §23.2/§23.15): el envío es de un documento mensual. No lleva
        ``manifest`` (``exchange.document`` exige UN recibo y el documento agrupa varios: el intento del documento
        guarda archivo y sha256); ``payslips`` son los recibos del documento y la evidencia se enlaza al documento
        por ``documento.exchange_ids``. Sin ``documento`` el comportamiento es el de siempre.
        """
        request = response.get('RawRequest', b'')
        answer = response.get('RawResponse', b'')
        if any(payslip.company_id != company for payslip in payslips):
            raise AccessError(_('Una evidencia DIAN no puede mezclar compañías.'))
        if documento:
            if manifest:
                raise ValueError('Una evidencia de un documento mensual no lleva manifiesto de recibos.')
            if documento.company_id != company:
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
                # .304: el número que viajó y el ambiente en que viajó, para que ``l10n.co.ne.consecutivo`` y los controles de consecutivo no dependan de leer el nombre del archivo.
                'numero': item['payslip'].l10n_co_ne_consecutive or False,
                'ambiente': company._ne_ambiente_consecutivos(),
                'sha256': hashlib.sha256(xml).hexdigest(),
                'signed_xml': self._binary(xml),
                'manifest_json': json.dumps({
                    'payslip_id': item['payslip'].id,
                    'cune': item['payslip'].l10n_co_ne_cune,
                    'file_name': item['filename'],
                    'sha256': hashlib.sha256(xml).hexdigest(),
                }, sort_keys=True),
            })
        if documento:
            documento.write({'exchange_ids': [(4, record.id)]})
        return record


class L10nCoNeExchangeDocument(models.Model):
    _name = 'l10n.co.ne.exchange.document'
    _check_company_auto = True      # H-F2-03 (C5)
    _description = 'Documento del manifiesto DIAN'
    _order = 'id'

    exchange_id = fields.Many2one('l10n.co.ne.exchange', required=True,
        readonly=True, ondelete='cascade', check_company=True)
    company_id = fields.Many2one(related='exchange_id.company_id', store=True,
        readonly=True, index=True)
    payslip_id = fields.Many2one('hr.payslip', required=True, readonly=True,
        ondelete='restrict', check_company=True)
    cune = fields.Char(readonly=True, index=True)
    file_name = fields.Char(required=True, readonly=True)
    numero = fields.Char(string='Número', readonly=True, index=True,
                         help='Consecutivo del documento que viajó en este envío (.304). Los manifiestos anteriores a .304 lo traen del nombre del archivo.')
    ambiente = fields.Selection([('habilitacion', 'Habilitación'), ('produccion', 'Producción')], string='Ambiente', readonly=True, index=True,
                                help='Ambiente DIAN en que viajó el envío (.304): los números de habilitación no cuentan contra los de producción.')
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
        """Inmutable. ÚNICA excepción (.304, condición del TL): el relleno de los manifiestos anteriores a .304 por la función de datos (``_ne_rellenar_numero_y_ambiente``), con el
        contexto explícito ``ne_rellenar_numero_ambiente``, SOLO los campos ``numero`` y ``ambiente`` y SOLO si todavía están vacíos (una vez). Cualquier otro cambio sigue rechazado."""
        if (self.env.context.get('ne_rellenar_numero_ambiente') and vals and set(vals) <= {'numero', 'ambiente'}
                and all(not manifiesto[campo] for manifiesto in self for campo in vals)):
            return super().write(vals)
        raise AccessError(_('El manifiesto DIAN es evidencia inmutable.'))

    @api.model
    def _ne_rellenar_numero_y_ambiente(self):
        """Función de datos (corre en cada ``-u``, .304): rellena ``numero`` (del nombre del archivo, ``ne_<NIT>_<consecutivo>.xml``) y ``ambiente`` (por el endpoint: el de producción de la
        compañía o habilitación) de los manifiestos que todavía no los traen. Es la única escritura permitida sobre un manifiesto, con contexto explícito y una sola vez."""
        for manifiesto in self.sudo().search(['|', ('numero', '=', False), ('ambiente', '=', False)]):
            valores = {}
            if not manifiesto.numero:
                numero = (manifiesto.file_name or '').rsplit('_', 1)[-1]
                numero = numero[:-4] if numero.lower().endswith('.xml') else numero
                if numero and numero[-1:].isdigit():
                    valores['numero'] = numero
            if not manifiesto.ambiente:
                compania = manifiesto.company_id
                valores['ambiente'] = 'produccion' if manifiesto.exchange_id.endpoint == compania._ne_dian_endpoint('1') else 'habilitacion'
            if valores:
                manifiesto.with_context(ne_rellenar_numero_ambiente=True).write(valores)
        return True

    def unlink(self):
        raise AccessError(_('El manifiesto DIAN no puede eliminarse automáticamente.'))
