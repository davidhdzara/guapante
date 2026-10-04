# -*- coding: utf-8 -*-
# Part of InSoTech. See LICENSE file for full copyright and licensing details.

"""
Asistente transaccional para procesar y enviar Nóminas Electrónicas a la DIAN
y recibos de pago en PDF por correo electrónico a los empleados.

Inspirado en la arquitectura nativa de facturación de Odoo 18 (account.move.send).
Permite procesamiento masivo e individual desde el formulario de nómina y la vista de lista.
"""

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrPayslipSend(models.TransientModel):
    """Asistente para firmar, transmitir a la DIAN y enviar nóminas por correo."""

    _name = 'hr.payslip.send'
    _description = 'Enviar y Procesar Nómina Electrónica'

    # ──────────────────────────────────────────────────────────────────
    # Relaciones y Configuración Base
    # ──────────────────────────────────────────────────────────────────
    payslip_ids = fields.Many2many(
        comodel_name='hr.payslip',
        string='Nóminas a Procesar',
        required=True,
    )
    mode = fields.Selection(
        selection=[
            ('single', 'Nómina Individual'),
            ('multi', 'Procesamiento Masivo'),
        ],
        string='Modo de Envío',
        compute='_compute_mode',
        store=True,
    )

    # ──────────────────────────────────────────────────────────────────
    # Opciones de Envío (DIAN & Email)
    # ──────────────────────────────────────────────────────────────────
    checkbox_send_dian = fields.Boolean(
        string='Enviar a la DIAN',
        default=True,
        help='Si está marcado, se generará el XML, se firmará digitalmente y se transmitirá '
             'al webservice de la DIAN para su aprobación oficial.',
    )
    checkbox_send_mail = fields.Boolean(
        string='Enviar por Correo al Empleado',
        compute='_compute_checkbox_send_mail',
        store=True,
        readonly=False,
        help='Si está marcado, se generará el PDF del comprobante y se enviará '
             'por correo electrónico al empleado utilizando la plantilla seleccionada.',
    )
    enable_send_mail = fields.Boolean(
        string='Permite Envío de Correo',
        compute='_compute_enable_send_mail',
    )
    mail_template_id = fields.Many2one(
        comodel_name='mail.template',
        string='Plantilla de Correo',
        domain="[('model', '=', 'hr.payslip')]",
        help='Plantilla de correo electrónico que se utilizará para estructurar el mensaje '
             'que se envía al empleado junto con su recibo de nómina en PDF.',
    )

    # ──────────────────────────────────────────────────────────────────
    # Computes y Defaults
    # ──────────────────────────────────────────────────────────────────
    @api.depends('payslip_ids')
    def _compute_mode(self):
        for rec in self:
            rec.mode = 'multi' if len(rec.payslip_ids) > 1 else 'single'

    @api.depends('payslip_ids')
    def _compute_enable_send_mail(self):
        for rec in self:
            # Habilitar correo si al menos una nómina pertenece a un empleado con correo de trabajo
            rec.enable_send_mail = any(p.employee_id.work_email for p in rec.payslip_ids)

    @api.depends('enable_send_mail')
    def _compute_checkbox_send_mail(self):
        for rec in self:
            rec.checkbox_send_mail = rec.enable_send_mail

    @api.model
    def default_get(self, fields_list):
        res = super(HrPayslipSend, self).default_get(fields_list)
        active_ids = self._context.get('active_ids')
        active_model = self._context.get('active_model')

        if active_model == 'hr.payslip' and active_ids:
            res['payslip_ids'] = [(6, 0, active_ids)]
            # Buscar una plantilla por defecto para hr.payslip
            template = self.env['mail.template'].search([('model', '=', 'hr.payslip')], limit=1)
            if template:
                res['mail_template_id'] = template.id
        return res

    # ──────────────────────────────────────────────────────────────────
    # Botón Principal: Ejecutar Procesamiento
    # ──────────────────────────────────────────────────────────────────
    def action_send_and_print(self):
        """Firma, transmite y envía las nóminas en lote o individualmente."""
        self.ensure_one()
        if not self.payslip_ids:
            raise UserError(_('No hay nóminas cargadas para procesar en el asistente.'))

        # Validación en procesamiento masivo: obligar a elegir plantilla de correo si está activo
        if self.mode == 'multi' and self.checkbox_send_mail and not self.mail_template_id:
            raise UserError(_(
                'Debe seleccionar una Plantilla de Correo para poder realizar el envío '
                'masivo de comprobantes de pago.'
            ))

        _logger.info(
            'Iniciando procesamiento de envío para %d nominas (DIAN: %s, Email: %s)',
            len(self.payslip_ids), self.checkbox_send_dian, self.checkbox_send_mail
        )

        for payslip in self.payslip_ids:
            # 1. Enviar a la DIAN (XML + SOAP) - Solo si requiere transmisión
            if self.checkbox_send_dian and payslip.l10n_co_ne_state in ('draft', 'generated', 'rejected'):
                try:
                    # Generar XML primero si está en borrador
                    if payslip.l10n_co_ne_state == 'draft':
                        payslip.action_generate_ne_xml()
                    
                    payslip.action_send_ne_dian()
                except Exception as e:
                    _logger.error(
                        'Fallo en transmision DIAN para nomina %s: %s',
                        payslip.number or payslip.name, str(e)
                    )
                    # Registramos el fallo en el chatter pero continuamos con el lote
                    payslip.message_post(
                        body=_('❌ <b>Error de transmisión automatizada:</b> %s') % str(e),
                        message_type='comment'
                    )

            # 2. Enviar por Correo Electrónico (PDF adjunto) - Solo si está Aceptado por la DIAN
            if self.checkbox_send_mail and payslip.employee_id.work_email:
                if payslip.l10n_co_ne_state == 'accepted':
                    try:
                        payslip.action_send_payslip_email(self.mail_template_id)
                    except Exception as e:
                        _logger.error(
                            'Fallo en envio de correo para nomina %s: %s',
                            payslip.number or payslip.name, str(e)
                        )
                        payslip.message_post(
                            body=_('⚠️ <b>Fallo al enviar correo al empleado:</b> %s') % str(e),
                            message_type='comment'
                        )
                else:
                    _logger.warning(
                        'No se envia correo para la nomina %s porque no ha sido aceptada por la DIAN (Estado actual: %s).',
                        payslip.number or payslip.name, payslip.l10n_co_ne_state
                    )

        return {'type': 'ir.actions.act_window_close'}

