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
    )
    documento_ids = fields.Many2many(
        comodel_name='l10n.co.ne.documento',
        string='Documentos mensuales',
        help='Documentos mensuales de nómina electrónica a preparar y enviar (entrada desde documentos).',
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
        string='DIAN',
        default=True,
        help='Si está marcado, se generará el XML, se firmará digitalmente y se transmitirá '
             'al webservice de la DIAN para su aprobación oficial.',
    )
    confirmo_mes_incompleto = fields.Boolean(
        string='Confirmo mes incompleto',
        help='Obligatorio si algún grupo avisa que el mes no ha terminado o faltan recibos: sin esta casilla ese grupo '
             'se prepara pero no se encola. Queda constancia en el documento (usuario y fecha).',
    )
    hay_confirmable = fields.Boolean(compute='_compute_resumen')
    confirmo_envio_extemporaneo = fields.Boolean(
        string='Confirmo envío extemporáneo',
        help='Obligatorio si la compañía bloquea el envío fuera de plazo y algún grupo ya venció: sin esta casilla ese '
             'grupo se prepara pero no se encola. Solo el administrador de nómina; queda constancia en el documento.')
    hay_extemporaneo = fields.Boolean(compute='_compute_resumen')
    resumen = fields.Html(string='Grupos y alertas', compute='_compute_resumen', sanitize=False)
    checkbox_send_representacion = fields.Boolean(
        string='Correo: representación gráfica y XML', default=False,
        help='Si está marcado, cuando la DIAN acepte el documento mensual se envía al empleado un ZIP con la '
             'representación gráfica (PDF con código QR) y el XML validado; si el documento ya está aceptado, se envía '
             'al momento. Es una comodidad de este módulo: el ZIP no es un contenedor definido por la DIAN, y la '
             'entrega de la representación no es obligatoria.')
    checkbox_send_mail = fields.Boolean(
        string='Correo: comprobante de pago',
        help='Si está marcado, se envía UN correo por empleado y fecha de pago con el comprobante de pago (PDF) de los '
             'recibos de ese pago, al correo del contacto de trabajo del empleado, por la cola de correo. Es un '
             'comprobante interno, independiente del estado ante la DIAN.',
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
    @api.depends('payslip_ids', 'documento_ids')
    def _compute_mode(self):
        for rec in self:
            rec.mode = 'multi' if len(rec.payslip_ids) + len(rec.documento_ids) > 1 else 'single'

    @api.depends('payslip_ids', 'documento_ids')
    def _compute_resumen(self):
        """Grupos (empleado + mes) y alertas del asistente. SOLO calcula: no crea documentos ni escribe nada."""
        Envio = self.env['l10n.co.ne.documento.send']
        for rec in self:
            produccion = rec.payslip_ids.filtered(lambda s: Envio._ne_es_produccion(s.company_id))
            documentos = rec.documento_ids
            grupos = Envio._ne_grupos(produccion, documentos) if (produccion or documentos) else []
            rec.resumen = Envio._ne_resumen(grupos) if grupos else False
            alertas = [a for g in grupos for a in Envio._ne_alertas_grupo(g)]
            rec.hay_confirmable = any(a['confirma'] == 'mes_incompleto' for a in alertas)
            rec.hay_extemporaneo = any(a['confirma'] == 'extemporaneo' for a in alertas)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self._context.get('active_ids')
        active_model = self._context.get('active_model')

        if active_model == 'l10n.co.ne.documento' and active_ids:
            res['documento_ids'] = [(6, 0, active_ids)]
        if active_model == 'hr.payslip' and active_ids:
            res['payslip_ids'] = [(6, 0, active_ids)]
            # Plantilla nativa por xmlid (nunca "la primera"); si falta, queda vacía y el envío da un error claro.
            template = self.env.ref(self.env['hr.payslip'].NE_MAIL_TEMPLATE_XMLID, raise_if_not_found=False)
            if template:
                res['mail_template_id'] = template.id
        return res

    # ──────────────────────────────────────────────────────────────────
    # Botón Principal: Ejecutar Procesamiento
    # ──────────────────────────────────────────────────────────────────
    def _ne_aviso_resultado(self, resumen, problemas, avisos):
        """Notificación nativa con el resultado: nada se traga en silencio (los problemas se listan)."""
        lineas = [resumen] + [_('Problema: %s', p) for p in problemas] + [_('Aviso: %s', a) for a in avisos]
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Enviar y Procesar'), 'message': '\n'.join(lineas),
                       'type': 'warning' if problemas else 'success', 'sticky': bool(problemas),
                       'next': {'type': 'ir.actions.act_window_close'}}}

    def action_send_and_print(self):
        """Transmite por recibo (ciclo de habilitación) y envía la colilla por correo; ambos independientes."""
        self.ensure_one()
        if not (self.payslip_ids or self.documento_ids):
            raise UserError(_('No hay recibos ni documentos cargados para procesar en el asistente.'))
        # Módulo inerte fuera de Colombia: error claro y no se crea nada.
        (self.payslip_ids.company_id | self.documento_ids.company_id)._ne_exigir_colombia()
        Envio = self.env['l10n.co.ne.documento.send']
        produccion = self.payslip_ids.filtered(lambda s: Envio._ne_es_produccion(s.company_id))
        habilitacion = self.payslip_ids - produccion
        resultado_docs = {'preparados': [], 'encolados': [], 'bloqueados': []}
        if produccion or self.documento_ids or (habilitacion and self.checkbox_send_dian):
            # H-F2-03: generar o transmitir el XML exige al administrador de nómina en TODOS los modos (también en habilitación), como el botón «Generar XML» del recibo.
            self.env['hr.payslip']._ne_exigir_administrador_de_nomina()
        if produccion or self.documento_ids:
            # Producción: el documento mensual (preparar y, si se marca "Enviar a la DIAN", generar y encolar).
            if self.checkbox_send_dian:
                Envio._ne_exigir_cron_activo()
            resultado_docs = Envio._ne_procesar(
                produccion, self.documento_ids, self.checkbox_send_dian, self.confirmo_mes_incompleto,
                self.confirmo_envio_extemporaneo)
        template = False
        if self.checkbox_send_mail:
            template = self.mail_template_id or self.env['hr.payslip']._ne_plantilla_colilla()
        problemas, avisos = [], []
        transmitidos = enviados = 0
        # Representación gráfica y XML por correo: solo documentos mensuales (producción), tras la aceptación de la DIAN.
        if self.checkbox_send_representacion:
            for documento in (produccion.l10n_co_ne_documento_id | self.documento_ids).filtered(
                    lambda d: not d.legacy and not d.eliminado):
                try:
                    aviso = documento._ne_solicitar_entrega_representacion()
                except Exception as error:
                    problemas.append(_('%(doc)s: no se pidió la representación gráfica (%(error)s).',
                                       doc=documento.display_name, error=error))
                    continue
                avisos.append(aviso or _('%s: la representación gráfica y el XML se envían al empleado cuando la DIAN '
                                         'acepte el documento (si ya está aceptado, se envió).', documento.display_name))

        for payslip in self.payslip_ids:
            nombre = payslip.number or payslip.name
            # 1. Ciclo DIAN por recibo: SOLO compañías en habilitación (producción va por documento). Un recibo que va en un documento mensual se transmite desde él.
            if self.checkbox_send_dian and payslip in habilitacion \
                    and payslip.l10n_co_ne_state in ('draft', 'generated', 'rejected'):
                doc = payslip.l10n_co_ne_documento_id
                if doc and not doc.legacy:
                    avisos.append(_('%(recibo)s: se transmite desde el documento mensual "%(doc)s".',
                                    recibo=nombre, doc=doc.display_name))
                else:
                    try:
                        if payslip.l10n_co_ne_state == 'draft':
                            payslip.action_generate_ne_xml()
                        payslip.action_send_ne_dian()
                        transmitidos += 1
                    except Exception as error:   # el lote sigue: el error se lista y queda en el chatter
                        _logger.error('Fallo en transmision DIAN para nomina %s: %s', nombre, error)
                        problemas.append(_('%(recibo)s: no se transmitió (%(error)s).', recibo=nombre, error=error))
                        payslip.message_post(
                            body=_('Error de transmisión automatizada: %s', error), message_type='comment')

        # 2. Comprobante de pago por correo: UN correo por (empleado, fecha de pago), sin depender del estado DIAN.
        if self.checkbox_send_mail:
            agrupados = self.env['hr.payslip']._ne_comprobantes(self.payslip_ids)
            for recibo, motivo in agrupados['sin_fecha']:
                problemas.append(_('%(recibo)s: no se envió el comprobante (%(motivo)s)',
                                   recibo=recibo.number or recibo.name, motivo=motivo))
            for grupo in agrupados['grupos']:
                recibos = grupo['recibos']
                nombre = '%s (%s)' % (grupo['empleado'].name, grupo['fecha_pago'])
                marca = self.env['hr.payslip'].NE_MARCA_CORREO_COMPROBANTE
                if recibos.message_ids.filtered(lambda m: m.body and marca in str(m.body)):
                    avisos.append(_('%s: ya se había enviado el comprobante de pago por correo antes.', nombre))
                try:
                    with self.env.cr.savepoint():
                        recibos.action_send_comprobante_email(template)
                    enviados += 1
                except Exception as error:
                    _logger.error('Fallo en envio de correo para el comprobante %s: %s', nombre, error)
                    problemas.append(_('%(grupo)s: no se envió el comprobante de pago (%(error)s).', grupo=nombre,
                                       error=error))
                    for recibo in recibos:
                        recibo.message_post(
                            body=_('Fallo al enviar el comprobante de pago por correo: %s', error),
                            message_type='comment')

        problemas += resultado_docs['bloqueados']
        resumen = _('Documentos: %(p)s preparados, %(c)s encolados, %(b)s bloqueados. Recibos: %(total)s; transmitidos '
                    'por recibo: %(t)s; comprobantes de pago encolados para envío: %(e)s.',
                    p=len(resultado_docs['preparados']), c=len(resultado_docs['encolados']),
                    b=len(resultado_docs['bloqueados']), total=len(self.payslip_ids), t=transmitidos, e=enviados)
        return self._ne_aviso_resultado(resumen, problemas, avisos)
