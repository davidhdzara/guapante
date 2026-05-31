# -*- coding: utf-8 -*-
"""
Wizard de exportacion de archivos planos bancarios.

Este wizard es el punto de entrada principal del modulo. Permite al usuario:
    1. Seleccionar pagos a proveedores o recibos de nomina.
    2. Elegir el banco destino y formato.
    3. Ver un reporte de validacion en tiempo real.
    4. Generar el archivo y descargarlo.
    5. Quedar con un registro de auditoria persistente.

El wizard nunca persiste; el registro de auditoria queda en bank.payment.export.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BankPaymentExportWizard(models.TransientModel):
    _name = 'bank.payment.export.wizard'
    _description = 'Exportar Archivo Plano Bancario'

    # =======================================================================
    # CAMPOS DE CONFIGURACION
    # =======================================================================

    bank = fields.Selection(
        selection=[
            ('davivienda',      'Banco Davivienda'),
            ('bogota',          'Banco de Bogota'),
            ('bancolombia_pab', 'Bancolombia - PAB (recomendado)'),
            ('bancolombia_sap', 'Bancolombia - SAP (legacy)'),
        ],
        string='Banco',
        required=True,
        default='davivienda',
        help='Banco al que se enviara el archivo.',
    )
    payment_source = fields.Selection(
        selection=[
            ('vendor',  'Pagos a Proveedores'),
            ('payroll', 'Nomina'),
            ('both',    'Proveedores y Nomina'),
        ],
        string='Origen del Pago',
        required=True,
        default='vendor',
    )

    # =======================================================================
    # REGISTROS A EXPORTAR
    # =======================================================================

    payment_ids = fields.Many2many(
        comodel_name='account.payment',
        string='Pagos a Proveedores',
        domain=[('payment_type', '=', 'outbound'), ('state', 'in', ('posted', 'in_process'))],
    )
    payslip_ids = fields.Many2many(
        comodel_name='hr.payslip',
        string='Recibos de Nomina',
        domain=[('state', 'in', ['done', 'paid'])],
    )

    # =======================================================================
    # RESUMEN COMPUTADO EN TIEMPO REAL
    # =======================================================================

    payment_count = fields.Integer(compute='_compute_summary')
    payslip_count = fields.Integer(compute='_compute_summary')
    total_amount = fields.Monetary(
        compute='_compute_summary',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    ready_count = fields.Integer(
        string='Listos para exportar',
        compute='_compute_validation',
    )
    error_count = fields.Integer(
        string='Con errores',
        compute='_compute_validation',
    )
    validation_html = fields.Html(
        string='Reporte de Validacion',
        compute='_compute_validation',
        sanitize=False,
    )

    # =======================================================================
    # RESULTADO DESPUES DE GENERAR
    # =======================================================================

    export_id = fields.Many2one(
        'bank.payment.export',
        readonly=True,
        help='Registro de auditoria creado al generar el archivo.',
    )
    excel_file = fields.Binary(
        related='export_id.excel_file',
        readonly=True,
    )
    excel_filename = fields.Char(
        related='export_id.excel_filename',
        readonly=True,
    )

    # =======================================================================
    # PRECARGA DESDE LISTA DE PAGOS O NOMINA
    # =======================================================================

    @api.model
    def default_get(self, fields_list):
        """
        Precarga los registros seleccionados cuando se abre el wizard
        desde el boton "Accion > Exportar Archivo Plano Bancario"
        en la vista de lista de pagos o nomina.
        """
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model', '')
        active_ids = self.env.context.get('active_ids', [])

        if active_model == 'account.payment' and active_ids:
            valid = self.env['account.payment'].browse(active_ids).filtered(
                lambda p: p.payment_type == 'outbound' and p.state in ('posted', 'in_process')
            )
            if not valid:
                raise UserError(_(
                    'Seleccione pagos de tipo Enviar en estado Publicado o En Proceso.'
                ))
            res.update({
                'payment_ids':    [(6, 0, valid.ids)],
                'payment_source': 'vendor',
            })

        elif active_model == 'hr.payslip' and active_ids:
            valid = self.env['hr.payslip'].browse(active_ids).filtered(
                lambda s: s.state in ('done', 'paid')
            )
            if not valid:
                raise UserError(_(
                    'Seleccione recibos de nomina en estado Hecho o Pagado.'
                ))
            res.update({
                'payslip_ids':    [(6, 0, valid.ids)],
                'payment_source': 'payroll',
            })

        return res

    # =======================================================================
    # COMPUTOS
    # =======================================================================

    @api.depends('payment_ids', 'payslip_ids', 'payment_source')
    def _compute_summary(self):
        """Calcula contadores y total para el panel de resumen."""
        for rec in self:
            payments = rec.payment_ids if rec.payment_source in ('vendor', 'both') \
                else rec.env['account.payment']
            payslips = rec.payslip_ids if rec.payment_source in ('payroll', 'both') \
                else rec.env['hr.payslip']
            rec.payment_count = len(payments)
            rec.payslip_count = len(payslips)
            rec.total_amount = (
                sum(payments.mapped('amount'))
                + sum(payslips.mapped('net_wage'))
            )

    @api.depends('payment_ids', 'payslip_ids', 'payment_source', 'bank')
    def _compute_validation(self):
        """
        Ejecuta la validacion en tiempo real contra el banco seleccionado.
        Genera un HTML con badges y tabla de errores para mostrar al usuario.
        """
        for rec in self:
            ready, errors = rec._get_validation_report()
            rec.ready_count = len(ready)
            rec.error_count = len(errors)
            rec.validation_html = rec._build_validation_html(ready, errors)

    def _get_validation_report(self):
        """
        Calcula el reporte de validacion para el banco seleccionado.

        Crea un registro temporal en memoria (con .new()) que NO se guarda
        en la base de datos, solo para reutilizar la logica de validacion
        del modelo bank.payment.export.

        Retorna: tupla (ready: list, errors: list of dict)
        """
        self.ensure_one()
        if not self.bank or (not self.payment_ids and not self.payslip_ids):
            return [], []

        # Registro en memoria para usar los metodos de validacion del banco
        export = self.env['bank.payment.export'].new({
            'bank':           self.bank,
            'payment_source': self.payment_source,
            'company_id':     self.env.company.id,
        })
        # Vincular registros sin persistir
        export.payment_ids = self.payment_ids
        export.payslip_ids = self.payslip_ids

        try:
            report = export.get_validation_report()
        except Exception as exc:
            # Falla en validacion - registrar como error general
            return [], [{
                'name':  'Sistema',
                'error': str(exc),
            }]

        return report.get('ready', []), report.get('errors', [])

    def _build_validation_html(self, ready, errors):
        """
        Construye el HTML del reporte de validacion.
        - Sin errores: muestra un badge verde con cuenta de listos.
        - Con errores: muestra tabla detallada con cada registro y su error.
        """
        if not errors and not ready:
            return ('<div class="alert alert-info" role="alert">'
                    'Seleccione registros para validar.</div>')

        if not errors:
            return (
                '<div class="alert alert-success" role="alert">'
                '<strong>%d registro(s) listos para exportar.</strong>'
                '</div>'
            ) % len(ready)

        # Hay errores: construir tabla
        rows = ''.join(
            '<tr>'
            '<td style="padding:4px 8px;border-bottom:1px solid #f0f0f0;">'
            '<strong>%s</strong></td>'
            '<td style="padding:4px 8px;border-bottom:1px solid #f0f0f0;'
            'color:#c0392b;">%s</td>'
            '</tr>' % (
                self._escape_html(e['name']),
                self._escape_html(e['error']),
            )
            for e in errors
        )
        return (
            '<div style="margin-bottom:8px;">'
            '<span class="badge badge-success">%d listos</span>&nbsp;'
            '<span class="badge badge-danger">%d con errores</span>'
            '</div>'
            '<table style="width:100%%;border-collapse:collapse;font-size:13px;">'
            '<thead><tr>'
            '<th style="text-align:left;padding:4px 8px;background:#f8f8f8;">'
            'Registro</th>'
            '<th style="text-align:left;padding:4px 8px;background:#f8f8f8;">'
            'Error</th>'
            '</tr></thead><tbody>%s</tbody></table>'
        ) % (len(ready), len(errors), rows)

    @staticmethod
    def _escape_html(text):
        """Escapa HTML para evitar inyeccion en el reporte."""
        if not text:
            return ''
        return (
            str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
        )

    # =======================================================================
    # VALIDACION DE LA SELECCION ANTES DE GENERAR
    # =======================================================================

    def _validate_selection(self):
        """Validacion de pre-condiciones antes de invocar el generador."""
        self.ensure_one()
        if self.payment_source in ('vendor', 'both') and not self.payment_ids:
            raise UserError(_('Seleccione al menos un pago a proveedor.'))
        if self.payment_source in ('payroll', 'both') and not self.payslip_ids:
            raise UserError(_('Seleccione al menos un recibo de nomina.'))
        if self.ready_count == 0:
            raise UserError(_(
                'Ninguno de los registros seleccionados esta listo para exportar. '
                'Revise el reporte de validacion y corrija los errores.'
            ))

    # =======================================================================
    # ACCIONES DEL WIZARD
    # =======================================================================

    def action_generate(self):
        """
        Genera el archivo plano y crea el registro de auditoria.
        Mantiene el wizard abierto para mostrar el enlace de descarga.
        """
        self.ensure_one()
        self._validate_selection()

        export = self.env['bank.payment.export'].create({
            'bank':           self.bank,
            'payment_source': self.payment_source,
            'payment_ids':    [(6, 0, self.payment_ids.ids)],
            'payslip_ids':    [(6, 0, self.payslip_ids.ids)],
        })
        try:
            export._generate_file()
        except Exception:
            export.unlink()
            raise
        self.export_id = export

        # Reabrir el wizard en el mismo estado para mostrar descarga
        return {
            'type':      'ir.actions.act_window',
            'res_model': 'bank.payment.export.wizard',
            'res_id':    self.id,
            'view_mode': 'form',
            'target':    'new',
        }

    def action_view_export(self):
        """Navega al registro de auditoria de esta exportacion."""
        self.ensure_one()
        if not self.export_id:
            raise UserError(_('No hay registro de exportacion para mostrar.'))
        return {
            'type':      'ir.actions.act_window',
            'res_model': 'bank.payment.export',
            'res_id':    self.export_id.id,
            'view_mode': 'form',
            'target':    'current',
        }
