import base64
import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class EmployeeCertificateIssuance(models.Model):
    _name = 'l10n_co.portal.employee.certificate.issuance'
    _description = 'Emisión de certificado laboral desde Portal'
    _order = 'issued_at desc, id desc'
    _rec_name = 'name'

    name = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    employee_id = fields.Many2one('hr.employee', required=True, readonly=True, index=True, ondelete='restrict')
    requesting_user_id = fields.Many2one('res.users', required=True, readonly=True, index=True, ondelete='restrict')
    certificate_type = fields.Selection([
        ('without_salary', 'Sin salario'), ('with_salary', 'Con salario'),
    ], required=True, readonly=True)
    issued_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    employee_name_snapshot = fields.Char(required=True, readonly=True)
    employee_document_snapshot = fields.Char(readonly=True)
    job_title_snapshot = fields.Char(readonly=True)
    start_date_snapshot = fields.Date(readonly=True)
    company_name_snapshot = fields.Char(required=True, readonly=True)
    wage_snapshot = fields.Monetary(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    signatory_name_snapshot = fields.Char(required=True, readonly=True)
    signatory_title_snapshot = fields.Char(required=True, readonly=True)
    # Keep the graphic snapshot in the issuance row, not as a generic attachment.
    signatory_signature_snapshot = fields.Binary(readonly=True, attachment=False)
    wage_periodicity_snapshot = fields.Char(readonly=True)
    template_version = fields.Char(required=True, readonly=True, default='18.0.2.0.0')
    checksum_sha256 = fields.Char(required=True, readonly=True, copy=False, index=True)
    attachment_id = fields.Many2one('ir.attachment', required=True, readonly=True, ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Las emisiones solo se crean desde el controlador autorizado.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_('Las emisiones son inmutables.'))
        return super().write(vals)

    @api.model
    def _validate_signatory(self, company):
        signatory = company.l10n_co_portal_certificate_signatory_employee_id.sudo()
        if (not signatory or not signatory.active or signatory.company_id != company
                or not company.l10n_co_portal_certificate_signatory_signature):
            raise UserError(_('La compañía no tiene firmante de certificados completo.'))
        return signatory

    @api.model
    def _active_contract(self, employee):
        contracts = self.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id), ('company_id', '=', employee.company_id.id),
            ('state', '=', 'open'),
        ], limit=2)
        if len(contracts) != 1:
            raise AccessError(_('No existe un contrato activo único para emitir este certificado.'))
        return contracts

    @api.model
    def _contract_pay_periodicity(self, contract):
        field = contract._fields.get('schedule_pay')
        if not field or not contract.schedule_pay:
            raise AccessError(_('El contrato activo no tiene una periodicidad de pago válida.'))
        selection = dict(field._description_selection(self.env))
        periodicity = selection.get(contract.schedule_pay)
        if not periodicity:
            raise AccessError(_('El contrato activo no tiene una periodicidad de pago válida.'))
        return periodicity

    @api.model
    def _render_certificate_pdf(self, issuance):
        report = self.env['ir.actions.report'].sudo().with_company(issuance.company_id).with_context(
            allowed_company_ids=[issuance.company_id.id],
        )
        return report._render_qweb_pdf(
            self.env.ref('l10n_co_portal_empleado.action_report_employee_certificate').id,
            [issuance.id],
        )

    @api.model
    def create_from_portal(self, employee, certificate_type, user=None):
        """Controller-only transactional boundary. The caller already established ownership."""
        user = user or self.env.user
        active_company = self.env.company
        if (certificate_type not in ('without_salary', 'with_salary') or not employee.active
                or employee.user_id != user or employee.company_id != active_company
                or active_company not in user.company_ids):
            raise AccessError(_('No fue posible emitir el certificado solicitado.'))
        company = employee.company_id.sudo()
        signatory = self._validate_signatory(company)
        sequence = self.env['ir.sequence'].sudo().with_company(company).next_by_code(
            'l10n_co.portal.employee.certificate.issuance'
        )
        if not sequence:
            raise UserError(_('No hay una secuencia configurada para emitir certificados laborales.'))
        vals = {
            'name': sequence,
            'company_id': company.id, 'employee_id': employee.id, 'requesting_user_id': user.id,
            'certificate_type': certificate_type, 'employee_name_snapshot': employee.name,
            'employee_document_snapshot': employee.identification_id,
            'job_title_snapshot': employee.job_id.name or employee.job_title,
            'start_date_snapshot': employee.first_contract_date,
            'company_name_snapshot': company.name,
            'signatory_name_snapshot': signatory.name,
            'signatory_title_snapshot': signatory.job_id.name or signatory.job_title or _('Responsable autorizado'),
            'signatory_signature_snapshot': company.l10n_co_portal_certificate_signatory_signature,
            'template_version': '18.0.2.0.0',
        }
        # The no-salary path intentionally does not query or populate a contract/currency/wage.
        if certificate_type == 'with_salary':
            contract = self._active_contract(employee)
            vals.update({
                'wage_snapshot': contract.wage,
                'currency_id': contract.currency_id.id,
                'wage_periodicity_snapshot': self._contract_pay_periodicity(contract),
            })
        # A savepoint makes a rendering/attachment error leave no visible issuance.
        with self.env.cr.savepoint():
            placeholder = self.env['ir.attachment'].sudo().create({
                'name': '%s.pdf' % vals['name'], 'type': 'binary', 'datas': b'',
                'mimetype': 'application/pdf', 'public': False, 'access_token': False,
                'res_model': self._name, 'res_id': 0,
            })
            issuance = self.sudo().create({**vals, 'checksum_sha256': 'pending', 'attachment_id': placeholder.id})
            pdf, _ = self._render_certificate_pdf(issuance)
            placeholder.sudo().write({
                'datas': base64.b64encode(pdf), 'res_id': issuance.id,
            })
            issuance.sudo().write({
                'checksum_sha256': hashlib.sha256(pdf).hexdigest(),
            })
        return issuance
