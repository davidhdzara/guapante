# -*- coding: utf-8 -*-
"""RADIAN Event tracking model.

Tracks DIAN RADIAN events (030-035) per invoice. This is a standalone
model (does NOT add fields to account.move) to comply with the rule
of not modifying native Odoo models.

Legal basis:
- Resolución 000165 de 2023 (mandatory events)
- Resolución 000008 de 2024 (Anexo 1.9)
"""

import logging
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class RadianEvent(models.Model):
    """Track RADIAN events for Colombian electronic invoices."""

    _name = 'insotech.radian.event'
    _description = 'Evento RADIAN'
    _order = 'event_date desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(
        string="Referencia",
        compute='_compute_name',
        store=True,
        help="Referencia auto-generada del evento.",
    )
    move_id = fields.Many2one(
        'account.move',
        string="Factura",
        required=True,
        ondelete='cascade',
        index=True,
        help="Factura electrónica asociada al evento.",
    )
    company_id = fields.Many2one(
        'res.company',
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
    )
    event_code = fields.Selection(
        selection=[
            ('030', '030 — Acuse de Recibo'),
            ('031', '031 — Rechazo de la FE'),
            ('032', '032 — Recibo de Bienes y Servicios'),
            ('033', '033 — Aceptación Expresa'),
            ('034', '034 — Reclamo de la FE'),
            ('035', '035 — Aceptación Tácita'),
        ],
        string="Código Evento",
        required=True,
        tracking=True,
        help="Código del evento RADIAN según catálogo DIAN.",
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('done', 'Generado'),
            ('sent', 'Enviado a DIAN'),
            ('accepted', 'Aceptado por DIAN'),
            ('error', 'Error'),
        ],
        string="Estado",
        default='draft',
        required=True,
        tracking=True,
        help="Estado del evento RADIAN.",
    )
    event_date = fields.Datetime(
        string="Fecha del Evento",
        default=fields.Datetime.now,
        required=True,
        help="Fecha y hora en que se generó el evento.",
    )
    xml_content = fields.Text(
        string="XML Generado (Dry Run)",
        help="Contenido del ApplicationResponse XML generado. "
             "En modo dry run, no se envía a la DIAN.",
    )
    notes = fields.Text(
        string="Notas",
        help="Notas adicionales o motivo del evento "
             "(ej: código de reclamo para evento 031).",
    )
    mandate_ip = fields.Char(
        string="IP Aprobación Mandato",
        readonly=True,
        help="Dirección IP pública del comprador que aceptó el mandato RADIAN en el portal.",
    )
    mandate_timestamp = fields.Datetime(
        string="Fecha Aprobación Mandato",
        readonly=True,
        help="Fecha y hora exacta en la que el usuario marcó el checkbox de autorización legal.",
    )
    source = fields.Selection(
        selection=[
            ('manual', 'Manual'),
            ('cron', 'Automático (CRON)'),
            ('portal', 'Portal Receptor'),
        ],
        string="Origen",
        default='manual',
        required=True,
        help="Cómo se generó este evento.",
    )
    claim_code = fields.Selection(
        selection=[
            ('01', '01 — Documento con inconsistencias'),
            ('02', '02 — Mercancía no entregada totalmente'),
            ('03', '03 — Mercancía no entregada parcialmente'),
            ('04', '04 — Servicio no prestado'),
        ],
        string="Concepto de Reclamo",
        help="Motivo del reclamo (solo para evento 034 — Reclamo).",
    )

    @api.depends('event_code', 'move_id')
    def _compute_name(self):
        """Generate a readable reference for the event."""
        for event in self:
            move_name = event.move_id.name or '???'
            code = event.event_code or '???'
            event.name = f"RAD-{code}/{move_name}"

    def _get_custom_holidays(self, company):
        """Get manual holidays for the given company as a set of dates.

        :param company: res.company record
        :returns: set of date objects
        """
        custom = self.env['insotech.custom.holiday'].search([
            ('company_id', '=', company.id),
        ])
        return {rec.date for rec in custom}

    @api.model
    def _cron_tacit_acceptance(self):
        """CRON: Generate tacit acceptance (035) events.

        Logic:
        1. Find all event 032 (Recibo del Bien/Servicio) records
        2. Check if 3 business days have passed since the 032
        3. Verify no event 033 (Aceptación Expresa),
           031 (Rechazo), or 034 (Reclamo) exists
        4. Create event 035 (Aceptación Tácita) in dry run

        IMPORTANT: The 3-day clock starts at event 032
        (Recibo del bien), NOT at 030 (Acuse de recibo).

        Legal basis: Resolución 000165/2023, art. 25
        Business days: Art. 62, Ley 4/1913
        """
        from ..services.colombian_calendar import add_business_days

        # Find all 032 events (Recibo del bien) — this is when
        # the 3-day clock starts per DIAN timeline
        recibo_events = self.search([
            ('event_code', '=', '032'),
            ('state', 'in', ('done', 'sent', 'accepted')),
        ])

        if not recibo_events:
            _logger.info(
                "Insotech RADIAN: No recibo events (032) found "
                "for tacit acceptance check."
            )
            return

        today = fields.Date.context_today(self)
        created_count = 0

        for recibo in recibo_events:
            move = recibo.move_id
            company = recibo.company_id

            # Check if this invoice already has a resolution event:
            # 033 (Aceptación Expresa), 035 (Aceptación Tácita),
            # 031 (Rechazo), or 034 (Reclamo)
            existing = self.search_count([
                ('move_id', '=', move.id),
                ('event_code', 'in', ('033', '035', '031', '034')),
                ('state', '!=', 'error'),
            ])
            if existing:
                continue

            # Calculate the deadline: 032 date + configurable days
            recibo_date = recibo.event_date.date()
            custom_holidays = self._get_custom_holidays(company)
            tacit_days = company.insotech_radian_tacit_days or 3
            deadline = add_business_days(
                recibo_date, tacit_days, custom_holidays,
            )

            if today <= deadline:
                # Not yet expired
                continue

            # 3 business days have passed — generate 035
            _logger.info(
                "Insotech RADIAN: Generating tacit acceptance "
                "(035) for invoice %s (recibo date: %s, "
                "deadline: %s, today: %s)",
                move.name, recibo_date, deadline, today,
            )

            tacit_event = self.create({
                'move_id': move.id,
                'company_id': company.id,
                'event_code': '035',
                'state': 'done',
                'source': 'cron',
                'notes': (
                    f"Aceptación tácita generada automáticamente. "
                    f"Recibo del bien (032) del {recibo_date}. "
                    f"Plazo venció el {deadline}."
                ),
            })
            tacit_event.action_send_to_dian()

            created_count += 1

        _logger.info(
            "Insotech RADIAN: Tacit acceptance CRON complete. "
            "Created %d event(s) 035.", created_count,
        )

    def action_send_to_dian(self):
        """Builds, signs, and sends the RADIAN structured XML to DIAN.
        
        Requires insotech_dian_wizard cryptographic tools.
        """
        try:
            from odoo.addons.insotech_dian_wizard.services import xml_signer, soap_client
            from ..services import radian_xml_builder
        except ImportError as e:
            _logger.error("RADIAN Send Error: requires insotech_dian_wizard installed. %s", e)
            return False

        for event in self:
            if event.state in ('accepted', 'sent'):
                continue

            company = event.company_id
            if not company.insotech_dian_cert_file or not company.insotech_dian_cert_password:
                event.write({'state': 'error', 'notes': 'Certificado .p12 no configurado en la compañía.'})
                continue

            try:
                # 0. Sync event_date to NOW so IssueDate == SigningTime
                #    DIAN rule AAD09e: "fecha de generación del evento
                #    debe ser igual a la fecha de firma del evento"
                event.event_date = datetime.now()

                # 1. Build context dict for pure XML builder
                from odoo.addons.insotech_core.utils.dian import (
                    get_partner_doc_type, clean_nit, compute_dv,
                )
                move = event.move_id
                seller_partner = company.partner_id
                buyer_partner = move.partner_id

                # Pre-process NIT + DV (builder is pure, receives clean data)
                seller_nit = clean_nit(seller_partner.vat or '')
                buyer_nit = clean_nit(buyer_partner.vat or '')

                ctx = {
                    'event_id': event.id,
                    'event_code': event.event_code,
                    'event_date': event.event_date,
                    'claim_code': event.claim_code if event.event_code == '034' else None,
                    'seller_nit': seller_nit,
                    'seller_name': seller_partner.name or '',
                    'seller_doc_type': get_partner_doc_type(seller_partner),
                    'seller_dv': compute_dv(seller_nit),
                    'buyer_nit': buyer_nit,
                    'buyer_name': buyer_partner.name or '',
                    'buyer_doc_type': get_partner_doc_type(buyer_partner),
                    'buyer_dv': compute_dv(buyer_nit),
                    'software_id': company.insotech_dian_software_id or '',
                    'software_pin': company.insotech_dian_software_pin or '',
                    'cufe': move.l10n_co_edi_cufe_cude_ref or '',
                    'invoice_number': move.name or '',
                    'test_mode': company.l10n_co_edi_test_mode,
                }


                # 2. Build Raw UBL 2.1 ApplicationResponse
                xml_string = radian_xml_builder.generate_application_response(ctx)

                xml_bytes = xml_string.encode('utf-8')

                # 2. Extract PIN and .p12 data
                import base64
                p12_b64 = company.insotech_dian_cert_file
                p12_bytes = base64.b64decode(p12_b64) if p12_b64 else b''
                p12_pass = company.insotech_dian_cert_password

                # 3. Apply XAdES-EPES Signature
                signed_xml_bytes = xml_signer.sign_xml(xml_bytes, p12_bytes, p12_pass)
                
                # Update dry-run tracker
                event.write({
                    'xml_content': signed_xml_bytes.decode('utf-8'),
                    'state': 'done',
                })

                # Determine production vs Hab endpoint correctly 
                # (usually hab matches the l10n_co_edi test flag, but we assume default from setup wizard or production)
                endpoint = 'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc'
                if company.l10n_co_edi_test_mode:
                    endpoint = 'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc'

                # 4. We must use SendEventUpdateStatus. soap_client.py doesn't have a direct wrapper for it.
                # However, _send_soap and _build_soap_envelope are available. 
                # Let's bypass SendBillSync wrapper and talk directly to the SOAP engine:
                SOAP_ACTION_EVENT = 'http://wcf.dian.colombia/IWcfDianCustomerServices/SendEventUpdateStatus'
                
                # Compress into ZIP for base64 as required by DIAN's SendEventUpdateStatus?
                # Actually, SendEventUpdateStatus accepts the same payload structure as SendBillSync (contentFile).
                import zipfile
                import io
                import base64
                
                # Filename MUST strictly use the 9-digit NIT (Sender), without DV.
                # DIAN extracts the sender's NIT from the characters after 'z'.
                # If company.vat is 9017972495 (10 digits), it causes a silent Code 89.
                clean_vat = str(company.vat).replace('-', '').replace(' ', '').replace('.', '').strip()
                if len(clean_vat) == 10 and clean_vat.isdigit():
                    # Check if it's a NIT (usually 10 digits means 9 + DV)
                    doc_type = getattr(company.partner_id.l10n_latam_identification_type_id, 'l10n_co_document_code', '31')
                    if str(doc_type) == '31':
                        clean_vat = clean_vat[:9]
                
                zip_buffer = io.BytesIO()
                # DIAN requires standard filename + .xml inside .zip.
                fe_num = str(event.id).zfill(6)
                xml_filename = f"z{clean_vat}000{fe_num}.xml"
                zip_filename = f"z{clean_vat}000{fe_num}.zip"
                
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr(xml_filename, signed_xml_bytes)
                
                base64_zip = base64.b64encode(zip_buffer.getvalue()).decode('ascii')
                
                # Payload:
                payload = f'''
                    <SendEventUpdateStatus xmlns="http://wcf.dian.colombia">
                        <contentFile>{base64_zip}</contentFile>
                    </SendEventUpdateStatus>
                '''
                
                # Load the DER certificate and private key from the .p12 binary
                private_key, cert_pem, cert_der, cert_obj = xml_signer.load_p12(p12_bytes, p12_pass)
                
                # Invoke SOAP client manually using WS-Security (_send handles envelope and parsing)
                result = soap_client._send(SOAP_ACTION_EVENT, endpoint, payload, cert_der, private_key)
                
                # Process the synchronous response
                is_valid = str(result.get('IsValid', 'false')).lower() == 'true'
                status_code = result.get('StatusCode', '')
                error_messages = result.get('ErrorMessages', '')
                status_msg = result.get('StatusMessage', '')
                raw_resp = result.get('RawResponse', '')
                
                if is_valid:
                    event.write({
                        'state': 'accepted',
                        'notes': f"DIAN Validado. StatusCode: {status_code}. {status_msg}",
                    })
                    # Add XML Attachment to the invoice (move)
                    self.env['ir.attachment'].create({
                        'name': f"ApplicationResponse_RAD_{event.event_code}_{move.name}.xml".replace('/', '_'),
                        'datas': base64.b64encode(signed_xml_bytes),
                        'res_model': 'account.move',
                        'res_id': move.id,
                        'mimetype': 'application/xml',
                    })
                    if result.get('ApplicationResponse'): # Attached official app response from DIAN
                        app_res_bytes = result['ApplicationResponse'].encode('utf-8')
                        self.env['ir.attachment'].create({
                            'name': f"Acuse_DIAN_RAD_{event.event_code}_{move.name}.xml".replace('/', '_'),
                            'datas': base64.b64encode(app_res_bytes),
                            'res_model': 'account.move',
                            'res_id': move.id,
                            'mimetype': 'application/xml',
                        })
                else:
                    err_str = f"Rechazado DIAN. Code {status_code}: {error_messages} | Msg: {status_msg}"
                    if not error_messages:
                        err_str += f" | RAW: {raw_resp}"
                    
                    event.write({
                        'state': 'error',
                        'notes': err_str,
                    })
                
            except Exception as e:
                _logger.exception("Failed to send RADIAN event to DIAN: %s", event.name)
                event.write({
                    'state': 'error',
                    'notes': f"Error interno en transmisión: {str(e)}",
                })
        return True
