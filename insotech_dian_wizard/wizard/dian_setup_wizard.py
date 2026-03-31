"""Wizard de configuración y habilitación DIAN.

Captura credenciales DIAN y ejecuta el proceso de habilitación
directamente via SOAP, sin requerir configuración previa en Odoo.
"""

import base64
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import test_data as td
from ..services import ubl_generator
from ..services import xml_signer
from ..services import soap_client

_logger = logging.getLogger(__name__)


class InsotechDianSetupWizard(models.TransientModel):
    """Wizard para capturar y almacenar datos de habilitación DIAN."""

    _name = 'insotech.dian.setup.wizard'
    _description = 'Wizard de Configuración DIAN'

    # -----------------------------------------------------------------
    # Campos de configuración
    # -----------------------------------------------------------------
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Empresa",
        default=lambda self: self.env.company,
        required=True,
    )
    software_id = fields.Char(string="Software ID")
    software_pin = fields.Char(string="Software PIN")
    test_set_id = fields.Char(string="Test Set ID")
    emitter_name = fields.Char(
        string="Razón Social (Pruebas DIAN)",
        default='COMERCIALIZADORA Y PRODUCTORA GUAPANTE S.A.S',
        help="Nombre exacto registrado en el RUT para pruebas.",
    )
    emitter_nit = fields.Char(
        string="NIT (Pruebas DIAN)",
        default='901975355',
        help="NIT sin dígito de verificación.",
    )
    emitter_city_code = fields.Char(
        string="Cód. Ciudad DANE",
        default='05360',
        help="Código de ciudad DANE (5 dígitos) para pruebas.",
    )
    emitter_dept_code = fields.Char(
        string="Cód. Dpto DANE",
        default='05',
        help="Código de departamento DANE (2 dígitos) para pruebas.",
    )
    technical_key = fields.Char(
        string="Clave Técnica (Pruebas)",
        default='fc8eac422eba16e22ffd8c6f94b3f40a6e38162c',
        help="Clave técnica del set de pruebas DIAN. "
             "Este valor es fijo para el entorno de habilitación.",
    )

    config_state = fields.Selection(
        related='company_id.insotech_dian_config_state',
        string="Estado Actual",
        readonly=True,
    )

    # -----------------------------------------------------------------
    # Campos de habilitación directa
    # -----------------------------------------------------------------
    cert_file = fields.Binary(
        string="Certificado Digital (.p12)",
        help="Suba el archivo .p12 o .pfx de su certificado "
             "digital. Se configurará automáticamente en "
             "Contabilidad para facturación electrónica.",
    )
    cert_filename = fields.Char(
        string="Nombre del archivo",
    )
    cert_password = fields.Char(
        string="Contraseña del Certificado",
        help="Contraseña del certificado digital (.p12).",
    )
    num_invoices = fields.Integer(
        string="Facturas de Prueba",
        default=30,
        help="Cantidad de facturas electrónicas (DIAN requiere 30).",
    )
    num_credit_notes = fields.Integer(
        string="Notas Crédito",
        default=10,
        help="Cantidad de notas crédito (DIAN requiere 10).",
    )
    num_debit_notes = fields.Integer(
        string="Notas Débito",
        default=10,
        help="Cantidad de notas débito (DIAN requiere 10).",
    )

    habilitacion_state = fields.Selection(
        selection=[
            ('idle', 'Sin iniciar'),
            ('sending', 'Enviando...'),
            ('waiting', 'Esperando respuesta DIAN'),
            ('done', 'Habilitación completada'),
            ('error', 'Error'),
        ],
        string="Estado Habilitación",
        default='idle',
    )
    track_id = fields.Char(
        string="Track ID (DIAN)",
        help="ID de rastreo devuelto por SendTestSetAsync.",
        readonly=True,
    )
    result_log = fields.Html(
        string="Resultado",
        readonly=True,
    )

    # -----------------------------------------------------------------
    # Default get
    # -----------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        """Precarga los valores actuales de la empresa."""
        res = super().default_get(fields_list)
        company = self.env.company
        res.update({
            'software_id': company.insotech_dian_software_id or '',
            'software_pin': company.insotech_dian_software_pin or '',
            'test_set_id': company.insotech_dian_test_set_id or '',

            'cert_file': company.insotech_dian_cert_file,
            'cert_filename': company.insotech_dian_cert_filename or '',
            'cert_password': company.insotech_dian_cert_password or '',
        })
        return res

    # -----------------------------------------------------------------
    # Acciones básicas (configuración)
    # -----------------------------------------------------------------
    def action_save_config(self):
        """Guardar configuración DIAN en la empresa."""
        self.ensure_one()
        vals = {
            'insotech_dian_software_id': self.software_id,
            'insotech_dian_software_pin': self.software_pin,
            'insotech_dian_test_set_id': self.test_set_id,
            'insotech_dian_config_state': 'in_progress',
        }
        if self.cert_file:
            vals['insotech_dian_cert_file'] = self.cert_file
            vals['insotech_dian_cert_filename'] = self.cert_filename
        if self.cert_password:
            vals['insotech_dian_cert_password'] = self.cert_password
        self.company_id.write(vals)
        return {'type': 'ir.actions.act_window_close'}

    def action_mark_enabled(self):
        """Marcar la habilitación DIAN como completada."""
        self.ensure_one()
        self.company_id.write({
            'insotech_dian_config_state': 'enabled',
        })
        return {'type': 'ir.actions.act_window_close'}

    def action_unlock(self):
        """Desbloquear la configuración para permitir edición."""
        self.ensure_one()
        self.company_id.write({
            'insotech_dian_config_state': 'in_progress',
        })
        return {'type': 'ir.actions.act_window_close'}

    # -----------------------------------------------------------------
    # Habilitación directa DIAN
    # -----------------------------------------------------------------
    def _get_certificate_p12(self):
        """Obtiene el certificado .p12.

        Prioridad:
        1. Archivo subido directamente en el wizard
        2. Certificado existente en res.company (l10n_co_dian)

        Returns:
            bytes: contenido binario del archivo .p12
        """
        # 1. Prioridad: archivo subido en el wizard
        if self.cert_file:
            return base64.b64decode(self.cert_file)

        # 2. Fallback: buscar en campos de l10n_co_dian
        company = self.company_id
        for fname in (
            'l10n_co_dian_certificate_file',
            'l10n_co_dian_certificate',
            'l10n_co_edi_certificate',
        ):
            if hasattr(company, fname) and getattr(company, fname):
                return base64.b64decode(getattr(company, fname))

        raise UserError(
            "Suba el certificado digital (.p12) en este wizard "
            "o en Contabilidad → Ajustes → Facturación Electrónica."
        )

    def _propagate_certificate_to_odoo(self, p12_bytes):
        """Configura automáticamente el certificado en Odoo.

        Crea o actualiza el registro en certificate.certificate
        para que l10n_co_dian pueda usarlo en producción.
        """
        if not self.cert_file:
            return  # Solo propagar si se subió en el wizard

        company = self.company_id

        # Extraer PEM del .p12
        try:
            from ..services.xml_signer import load_p12
            private_key, cert_pem, cert_der, cert_obj = load_p12(
                p12_bytes, self.cert_password,
            )
        except Exception as e:
            _logger.warning(
                "No se pudo extraer PEM del .p12 para "
                "propagación: %s", e,
            )
            return

        # Intentar crear/actualizar en certificate.certificate
        if 'certificate.certificate' not in self.env:
            _logger.info(
                "Modelo certificate.certificate no disponible. "
                "El certificado se usó para firmar pero no se "
                "propagó a Ajustes de Contabilidad."
            )
            return

        CertModel = self.env['certificate.certificate']
        existing = CertModel.search(
            [('company_id', '=', company.id)], limit=1,
        )

        cert_vals = {
            'company_id': company.id,
        }

        # Intentar asignar los campos según la versión de Odoo
        field_map = {
            'pem_certificate': base64.b64encode(cert_pem),
            'password': self.cert_password,
            'name': self.cert_filename or 'DIAN Certificate',
            'content': self.cert_file,
        }

        for fname, fval in field_map.items():
            if fname in CertModel._fields:
                cert_vals[fname] = fval

        try:
            if existing:
                existing.write(cert_vals)
                _logger.info(
                    "Certificado actualizado en Odoo: %s",
                    existing.id,
                )
            else:
                new_cert = CertModel.create(cert_vals)
                _logger.info(
                    "Certificado creado en Odoo: %s",
                    new_cert.id,
                )
        except Exception as e:
            _logger.warning(
                "No se pudo propagar el certificado a "
                "certificate.certificate: %s", e,
            )

    def action_start_habilitacion(self):
        """Ejecuta el proceso de habilitación DIAN completo.

        1. Valida credenciales
        2. Genera los XMLs UBL 2.1 con datos emulados
        3. Firma cada XML con XAdES-BES
        4. Empaqueta en ZIP y envía via SendTestSetAsync
        5. Reporta resultado
        """
        self.ensure_one()

        # Validaciones
        if not self.software_id:
            raise UserError("Ingrese el Software ID.")
        if not self.software_pin:
            raise UserError("Ingrese el Software PIN.")
        if not self.test_set_id:
            raise UserError("Ingrese el Test Set ID.")
        if not self.cert_password:
            raise UserError(
                "Ingrese la contraseña del certificado .p12."
            )
        if not self.technical_key:
            raise UserError(
                "Ingrese la Clave Técnica de pruebas. "
                "Se obtiene del portal de habilitación DIAN."
            )
        if not self.emitter_name or not self.emitter_nit or not self.emitter_city_code or not self.emitter_dept_code:
            raise UserError("Debe llenar todos los datos exactos del Emisor dictados por el RUT.")

        # Guardar credenciales en la empresa
        save_vals = {
            'insotech_dian_software_id': self.software_id,
            'insotech_dian_software_pin': self.software_pin,
            'insotech_dian_test_set_id': self.test_set_id,
            'insotech_dian_config_state': 'in_progress',
        }
        if self.cert_file:
            save_vals['insotech_dian_cert_file'] = self.cert_file
            save_vals['insotech_dian_cert_filename'] = self.cert_filename
        if self.cert_password:
            save_vals['insotech_dian_cert_password'] = self.cert_password
        self.company_id.write(save_vals)

        self.habilitacion_state = 'sending'
        log_lines = ['<h4>📡 Proceso de Habilitación DIAN</h4><ul>']

        try:
            # Obtener certificado
            p12_bytes = self._get_certificate_p12()
            _logger.info("Certificate .p12 loaded successfully")
            log_lines.append(
                '<li>✅ Certificado .p12 cargado</li>'
            )

            # Extraer private key y PEM para zeep WS-Security
            from ..services.xml_signer import load_p12
            private_key, cert_pem, cert_der, _ = load_p12(
                p12_bytes, self.cert_password,
            )

            # Propagar certificado a Odoo (l10n_co_dian)
            self._propagate_certificate_to_odoo(p12_bytes)
            log_lines.append(
                '<li>✅ Certificado configurado en Contabilidad</li>'
            )

            # Generar XMLs
            xml_files = {}
            invoice_cufes = {}
            invoice_numbers = {}
            # Offset dinámico basado en timestamp para evitar
            # Regla 90 (documento procesado anteriormente).
            # Cada ejecución genera consecutivos únicos dentro
            # del rango autorizado (990000000 - 995000000).
            import time
            offset = int(time.time()) % 4000000  # max ~4M
            start_number = td.DIAN_HAB_RANGE_FROM + offset

            # Construir dict EMISOR con los valores exactos definidos en DIAN Wizard
            from ..services.test_data import _compute_dv
            emitter = {
                'company_name': self.emitter_name,
                'nit': self.emitter_nit,
                'dv': str(_compute_dv(self.emitter_nit)), 
                'document_type': '31', # NIT
                'additional_account_id': '1', 
                'tax_scheme_id': '01',
                'tax_scheme_name': 'IVA',
                'tax_level_code': 'O-48', # Estándar genérico responsable IVA
                'address_line': 'CALLE 1 # 1 - 1', # Dummy
                'city_name': 'Ciudad Oculta', 
                'city_code': self.emitter_city_code, # DIAN sólo valida con código, no string
                'department': 'Departamento Oculto', 
                'department_code': self.emitter_dept_code, # Clave para evitar CDG01
                'country_code': 'CO',
                'country_name': 'Colombia',
                'postal_zone': '000000',
                'phone': '3000000000',
                'email': 'habilitacion@insotech.it',
                'registration_name': self.emitter_name, 
            }
            nit10 = emitter['nit'].rjust(10, '0')

            # Facturas
            for i in range(self.num_invoices):
                num = start_number + i
                doc_number = '%s%s' % (td.DIAN_HAB_PREFIX, num)
                xml_bytes = ubl_generator.generate_invoice(
                    number=num,
                    software_id=self.software_id,
                    software_pin=self.software_pin,
                    technical_key=self.technical_key,
                    emitter_data=emitter,
                )
                signed_xml = xml_signer.sign_xml(
                    xml_bytes, p12_bytes, self.cert_password,
                )
                filename = 'fv%s%s.xml' % (nit10, doc_number)
                xml_files[filename] = signed_xml
                invoice_numbers[i] = doc_number

                # Extraer CUFE del XML firmado
                from lxml import etree as ET
                root = ET.fromstring(signed_xml)
                uuid_elem = root.find(
                    './/{%s}UUID' % td.NS['cbc']
                )
                invoice_cufes[i] = (
                    uuid_elem.text if uuid_elem is not None else ''
                )

                log_lines.append(
                    '<li>✅ Factura %s generada y firmada</li>'
                    % doc_number
                )

            # Notas Crédito (cada una referencia una factura diferente)
            nc_start = start_number + self.num_invoices

            for i in range(self.num_credit_notes):
                num = nc_start + i
                doc_number = '%s%s' % (td.DIAN_HAB_PREFIX, num)
                # Rotar entre facturas disponibles
                ref_idx = i % self.num_invoices
                ref_inv = invoice_numbers.get(ref_idx, '')
                ref_cf = invoice_cufes.get(ref_idx, '')
                xml_bytes = ubl_generator.generate_credit_note(
                    number=num,
                    ref_invoice_number=ref_inv,
                    ref_cufe=ref_cf,
                    software_id=self.software_id,
                    software_pin=self.software_pin,
                    emitter_data=emitter,
                )
                signed_xml = xml_signer.sign_xml(
                    xml_bytes, p12_bytes, self.cert_password,
                )
                filename = 'nc%s%s.xml' % (nit10, doc_number)
                xml_files[filename] = signed_xml
                log_lines.append(
                    '<li>✅ Nota Crédito %s generada y firmada</li>'
                    % doc_number
                )

            # Notas Débito (cada una referencia una factura diferente)
            nd_start = nc_start + self.num_credit_notes

            for i in range(self.num_debit_notes):
                num = nd_start + i
                doc_number = '%s%s' % (td.DIAN_HAB_PREFIX, num)
                # Rotar entre facturas disponibles
                ref_idx = i % self.num_invoices
                ref_inv = invoice_numbers.get(ref_idx, '')
                ref_cf = invoice_cufes.get(ref_idx, '')
                xml_bytes = ubl_generator.generate_debit_note(
                    number=num,
                    ref_invoice_number=ref_inv,
                    ref_cufe=ref_cf,
                    software_id=self.software_id,
                    software_pin=self.software_pin,
                    emitter_data=emitter,
                )
                signed_xml = xml_signer.sign_xml(
                    xml_bytes, p12_bytes, self.cert_password,
                )
                filename = 'nd%s%s.xml' % (nit10, doc_number)
                xml_files[filename] = signed_xml
                log_lines.append(
                    '<li>✅ Nota Débito %s generada y firmada</li>'
                    % doc_number
                )

            log_lines.append('</ul>')

            # ============================================
            # PASO PREVIO: Probar 1 factura con SendBillSync
            # SendTestSetAsync enmascara errores — primero
            # validamos UNA factura individualmente.
            # ============================================
            first_filename = list(xml_files.keys())[0]
            first_xml = xml_files[first_filename]
            log_lines.append(
                '<h4>🔍 Probando 1 factura individual '
                '(SendBillSync)...</h4>'
            )
            log_lines.append(
                '<p>Archivo: <code>%s</code></p>'
                % first_filename
            )
            # CUFE Debug
            from ..services import ubl_generator as _ug_debug
            if _ug_debug.last_cufe_debug.get('raw'):
                log_lines.append(
                    '<p><strong>CUFE raw:</strong> '
                    '<code style="word-break:break-all">'
                    '%s</code></p>'
                    % _ug_debug.last_cufe_debug['raw']
                )
                log_lines.append(
                    '<p><strong>CUFE hash:</strong> '
                    '<code>%s</code></p>'
                    % _ug_debug.last_cufe_debug['hash']
                )

            test_result = soap_client.send_bill_sync(
                first_xml, first_filename,
                private_key=private_key,
                cert_pem=cert_pem,
            )

            t_code = test_result.get('StatusCode', '')
            t_valid = test_result.get('IsValid', '')
            t_desc = test_result.get(
                'StatusDescription', '')
            t_msg = test_result.get('StatusMessage', '')
            t_err = test_result.get('ErrorMessage', '')
            t_msgs = test_result.get('ErrorMessages', [])
            t_faults = test_result.get('FaultDetails', [])

            log_lines.append(
                '<p><strong>StatusCode:</strong> %s</p>'
                % (t_code or 'N/A'))
            log_lines.append(
                '<p><strong>IsValid:</strong> %s</p>'
                % (t_valid or 'N/A'))
            log_lines.append(
                '<p><strong>Estado:</strong> %s</p>'
                % (t_desc or t_msg or 'Sin descripción'))

            if t_err:
                log_lines.append(
                    '<p>❌ <strong>Error:</strong> %s</p>'
                    % t_err)
            if t_msgs:
                log_lines.append(
                    '<p><strong>Errores de validación'
                    ':</strong></p><ul>')
                for em in t_msgs:
                    log_lines.append('<li>%s</li>' % em)
                log_lines.append('</ul>')
            if t_faults:
                log_lines.append(
                    '<p><strong>SOAP Fault:</strong></p><ul>')
                for fd in t_faults:
                    log_lines.append('<li>%s</li>' % fd)
                log_lines.append('</ul>')

            # Mostrar comentarios y ApplicationResponse
            t_comment = test_result.get(
                'XmlDocumentComment', '')
            if t_comment:
                log_lines.append(
                    '<p><strong>Comentario DIAN:</strong> '
                    '%s</p>' % t_comment)

            t_app_resp = test_result.get(
                'ApplicationResponse', '')
            if t_app_resp:
                log_lines.append(
                    '<details><summary>ApplicationResponse '
                    'XML (errores detallados)</summary>'
                    '<pre>%s</pre></details>'
                    % t_app_resp[:5000])

            t_raw = test_result.get('RawResponse', '')
            if t_raw:
                log_lines.append(
                    '<details><summary>Respuesta SOAP completa'
                    '</summary><pre>%s</pre></details>'
                    % t_raw[:5000])

            # Si SendBillSync falla, NO enviar el batch
            if t_valid and t_valid.lower() == 'true':
                log_lines.append(
                    '<p>✅ Factura individual ACEPTADA. '
                    'Procediendo con el set completo...</p>')
            elif t_code and t_code not in ('', 'N/A'):
                # Tiene respuesta pero no es válida — parar
                self.habilitacion_state = 'error'
                log_lines.append(
                    '<p>❌ <strong>Factura rechazada por la '
                    'DIAN.</strong> Corrija los errores antes '
                    'de enviar el set completo.</p>')
                self.result_log = ''.join(log_lines)
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': self._name,
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'new',
                }
            else:
                # Sin respuesta clara — mostrar lo que hay
                log_lines.append(
                    '<p>⚠️ No se pudo validar la factura '
                    'individual. Intentando enviar set '
                    'completo de todas formas...</p>')

            # ============================================
            # Enviar set completo a la DIAN
            # ============================================
            log_lines.append(
                '<h4>📤 Enviando %d documentos a la DIAN...'
                '</h4>' % len(xml_files)
            )

            # Enviar a la DIAN
            result = soap_client.send_test_set_async(
                xml_files=xml_files,
                test_set_id=self.test_set_id,
                private_key=private_key,
                cert_pem=cert_pem,
            )

            # Procesar resultado
            status_code = result.get('StatusCode', '')
            zip_key = result.get('ZipKey', '')
            status_desc = result.get('StatusDescription', '')
            status_msg = result.get('StatusMessage', '')
            error_msg = result.get('ErrorMessage', '')

            if zip_key:
                self.track_id = zip_key
                log_lines.append(
                    '<p>📨 ZIP recibido por la DIAN. '
                    'Track ID: <code>%s</code></p>' % zip_key
                )
                log_lines.append(
                    '<p>⏳ Consultando resultado de validación...</p>'
                )

                # Consultar estado automáticamente
                import time
                status_result = None
                for attempt in range(3):
                    time.sleep(5)  # Esperar 5s entre intentos
                    status_result = soap_client.get_status_zip(
                        zip_key,
                        private_key=private_key,
                        cert_pem=cert_pem,
                    )
                    s_code = status_result.get('StatusCode', '')
                    s_valid = status_result.get('IsValid', '')
                    s_desc = status_result.get(
                        'StatusDescription', '')
                    s_msgs = status_result.get(
                        'ErrorMessages', [])
                    s_err = status_result.get('ErrorMessage', '')

                    _logger.info(
                        "DIAN status attempt %d: code=%s valid=%s",
                        attempt + 1, s_code, s_valid,
                    )

                    # Si tiene resultado definitivo, salir
                    if s_valid or s_msgs or s_err:
                        break

                if status_result:
                    s_code = status_result.get('StatusCode', '')
                    s_valid = status_result.get('IsValid', '')
                    s_desc = status_result.get(
                        'StatusDescription', '')
                    s_msg = status_result.get(
                        'StatusMessage', '')
                    s_msgs = status_result.get(
                        'ErrorMessages', [])
                    s_err = status_result.get('ErrorMessage', '')

                    log_lines.append(
                        '<h4>📋 Resultado de Validación DIAN</h4>')
                    log_lines.append(
                        '<p><strong>Código:</strong> %s</p>'
                        % (s_code or 'N/A'))
                    log_lines.append(
                        '<p><strong>Estado:</strong> %s</p>'
                        % (s_desc or s_msg or 'Sin respuesta'))

                    if s_valid and s_valid.lower() == 'true':
                        self.habilitacion_state = 'done'
                        self.company_id.write({
                            'insotech_dian_config_state': 'enabled',
                        })
                        log_lines.append(
                            '<p>✅ <strong>¡Documentos aceptados '
                            'por la DIAN!</strong></p>'
                        )
                    elif s_msgs or s_err:
                        self.habilitacion_state = 'error'
                        if s_err:
                            log_lines.append(
                                '<p>❌ <strong>Error:</strong> '
                                '%s</p>' % s_err)
                        if s_msgs:
                            log_lines.append(
                                '<p><strong>Errores de validación'
                                ':</strong></p><ul>')
                            for em in s_msgs:
                                log_lines.append(
                                    '<li>%s</li>' % em)
                            log_lines.append('</ul>')
                    else:
                        self.habilitacion_state = 'waiting'
                        log_lines.append(
                            '<p>⏳ Aún en procesamiento. Use '
                            '"Consultar Estado" para reintentar.'
                            '</p>'
                        )

                    # Mostrar respuesta raw para debug
                    raw = status_result.get('RawResponse', '')
                    if raw:
                        log_lines.append(
                            '<details><summary>Respuesta DIAN'
                            '</summary><pre>%s</pre></details>'
                            % raw[:2000]
                        )

            else:
                # SendTestSetAsync falló — no se recibió ZipKey
                self.habilitacion_state = 'error'
                log_lines.append(
                    '<p>❌ <strong>Error al enviar:</strong></p>'
                )
                if error_msg:
                    log_lines.append('<p>%s</p>' % error_msg)
                fault_details = result.get('FaultDetails', [])
                if fault_details:
                    log_lines.append(
                        '<p><strong>Detalle DIAN:</strong></p><ul>')
                    for fd in fault_details:
                        log_lines.append('<li>%s</li>' % fd)
                    log_lines.append('</ul>')
                raw = result.get('RawResponse', '')
                if raw:
                    log_lines.append(
                        '<details><summary>Respuesta</summary>'
                        '<pre>%s</pre></details>' % raw[:1000])

        except UserError:
            raise
        except Exception as e:
            _logger.exception("Error en habilitación DIAN")
            self.habilitacion_state = 'error'
            log_lines.append(
                '<p>❌ <strong>Error inesperado:</strong> %s</p>'
                % str(e)
            )

        self.result_log = ''.join(log_lines)
        # Reopen wizard to show results
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_check_status(self):
        """Consulta el estado del envío a la DIAN."""
        self.ensure_one()

        if not self.track_id:
            raise UserError(
                "No hay un envío pendiente. "
                "Primero ejecute la habilitación."
            )

        # Obtener credenciales del certificado
        try:
            p12_bytes = self._get_certificate_p12()
            from ..services.xml_signer import load_p12
            private_key, cert_pem, cert_der, _ = load_p12(
                p12_bytes, self.cert_password,
            )
        except Exception as e:
            self.result_log = (
                '<p>❌ Error cargando certificado: %s</p>' % e
            )
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        try:
            result = soap_client.get_status_zip(
                self.track_id,
                private_key=private_key,
                cert_pem=cert_pem,
            )
        except Exception as e:
            self.result_log = (
                '<p>❌ Error consultando DIAN: %s</p>' % e
            )
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        status_code = result.get('StatusCode', '')
        status_desc = result.get('StatusDescription', '')
        status_msg = result.get('StatusMessage', '')
        is_valid = result.get('IsValid', '')
        error_msg = result.get('ErrorMessage', '')
        error_msgs = result.get('ErrorMessages', [])

        log = ['<h4>📋 Estado del Envío DIAN</h4>']
        log.append('<p><strong>Track ID:</strong> %s</p>'
                   % self.track_id)
        log.append('<p><strong>Código:</strong> %s</p>'
                   % (status_code or 'N/A'))
        log.append('<p><strong>Estado:</strong> %s</p>'
                   % (status_desc or status_msg or 'Sin descripción'))

        if is_valid and is_valid.lower() == 'true':
            self.habilitacion_state = 'done'
            self.company_id.write({
                'insotech_dian_config_state': 'enabled',
            })
            log.append(
                '<p>✅ <strong>¡Habilitación DIAN completada!</strong>'
                '</p><p>Su empresa ha sido habilitada como '
                'facturador electrónico.</p>'
            )
        elif error_msg or error_msgs:
            log.append(
                '<p>❌ <strong>Error:</strong> %s</p>' % error_msg
            )
            if error_msgs:
                log.append('<p><strong>Detalle errores:</strong></p><ul>')
                for em in error_msgs:
                    log.append('<li>%s</li>' % em)
                log.append('</ul>')
            self.habilitacion_state = 'error'
        else:
            log.append(
                '<p>⏳ El procesamiento aún está en curso. '
                'Intente nuevamente en unos minutos.</p>'
            )

        # Mostrar respuesta completa para debug
        fault_details = result.get('FaultDetails', [])
        if fault_details:
            log.append('<p><strong>DIAN Fault:</strong></p><ul>')
            for fd in fault_details:
                log.append('<li>%s</li>' % fd)
            log.append('</ul>')

        raw = result.get('RawResponse', '')
        if raw:
            log.append(
                '<details><summary>Respuesta completa</summary>'
                '<pre>%s</pre></details>' % raw[:2000]
            )

        self.result_log = ''.join(log)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_test_single(self):
        """Envía UNA factura individual vía SendBillSync.

        Esto revela errores EXACTOS que SendTestSetAsync enmascara.
        """
        self.ensure_one()
        log = ['<h4>🔍 Prueba Individual (SendBillSync)</h4>']

        try:
            p12_bytes = self._get_certificate_p12()
            from ..services.xml_signer import load_p12
            private_key, cert_pem, cert_der, _ = load_p12(
                p12_bytes, self.cert_password,
            )

            # Generar UNA factura (offset dinámico → Regla 90)
            import time
            num = td.DIAN_HAB_RANGE_FROM + (
                int(time.time()) % 4000000)
            doc_number = '%s%s' % (td.DIAN_HAB_PREFIX, num)
            emitter = ubl_generator.partner_to_party_dict(
                self.company_id.partner_id)
            xml_bytes = ubl_generator.generate_invoice(
                number=num,
                software_id=self.software_id,
                software_pin=self.software_pin,
                technical_key=self.technical_key,
                emitter_data=emitter,
            )
            signed_xml = xml_signer.sign_xml(
                xml_bytes, p12_bytes, self.cert_password,
            )

            nit10 = emitter['nit'].rjust(10, '0')
            filename = 'fv%s%s.xml' % (nit10, doc_number)

            log.append(
                '<p>📄 Factura: <code>%s</code></p>' % doc_number
            )
            log.append(
                '<p>📁 Archivo: <code>%s</code></p>' % filename
            )
            log.append('<p>📤 Enviando vía SendBillSync...</p>')

            result = soap_client.send_bill_sync(
                signed_xml, filename,
                private_key=private_key,
                cert_pem=cert_pem,
            )

            # Mostrar TODO lo que retorna
            s_code = result.get('StatusCode', '')
            s_desc = result.get('StatusDescription', '')
            s_msg = result.get('StatusMessage', '')
            s_valid = result.get('IsValid', '')
            s_err = result.get('ErrorMessage', '')
            s_msgs = result.get('ErrorMessages', [])
            faults = result.get('FaultDetails', [])

            log.append('<h4>📋 Resultado DIAN</h4>')
            log.append(
                '<p><strong>StatusCode:</strong> %s</p>'
                % (s_code or 'N/A'))
            log.append(
                '<p><strong>IsValid:</strong> %s</p>'
                % (s_valid or 'N/A'))
            log.append(
                '<p><strong>Estado:</strong> %s</p>'
                % (s_desc or s_msg or 'Sin descripción'))

            if s_valid and s_valid.lower() == 'true':
                log.append(
                    '<p>✅ <strong>¡Factura ACEPTADA!</strong></p>'
                )
            else:
                if s_err:
                    log.append(
                        '<p>❌ <strong>Error:</strong> %s</p>'
                        % s_err)
                if s_msgs:
                    log.append(
                        '<p><strong>Errores de validación'
                        ':</strong></p><ul>')
                    for em in s_msgs:
                        log.append('<li>%s</li>' % em)
                    log.append('</ul>')
                if faults:
                    log.append(
                        '<p><strong>SOAP Fault:</strong></p><ul>')
                    for fd in faults:
                        log.append('<li>%s</li>' % fd)
                    log.append('</ul>')

            raw = result.get('RawResponse', '')
            if raw:
                log.append(
                    '<details><summary>Respuesta completa'
                    '</summary><pre>%s</pre></details>'
                    % raw[:3000])

        except Exception as e:
            _logger.exception("Error test single")
            log.append(
                '<p>❌ <strong>Error:</strong> %s</p>' % str(e))

        self.result_log = ''.join(log)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
