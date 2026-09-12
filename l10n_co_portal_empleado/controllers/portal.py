import base64

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request


class EmployeePortal(http.Controller):
    """Routes intentionally have no employee/company identifiers as authority."""

    def _employee_or_not_found(self):
        allowed_companies = request.env.companies & request.env.user.company_ids
        employees = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.user.id), ('active', '=', True),
            ('company_id', 'in', allowed_companies.ids)], limit=2)
        if len(employees) != 1:
            return None
        return employees

    def _portal_values(self, employee):
        # sudo is deliberately only reached after the exact user_id match above.
        employee = employee.sudo()
        company = employee.company_id.sudo()
        return {
            'profile': {
                'name': employee.name,
                'image': employee.image_1920,
                'job': employee.job_id.name or employee.job_title,
                'department': employee.department_id.name,
                'company': company.name,
                'work_email': employee.work_email,
                'work_phone': employee.work_phone,
                'mobile_phone': employee.mobile_phone,
                'address': employee.address_id.contact_address,
                'private_email': employee.private_email,
                'private_phone': employee.private_phone,
                'emergency_contact': employee.emergency_contact,
                'emergency_phone': employee.emergency_phone,
                'emergency_relationship': employee.portal_emergency_relationship,
                'street': employee.address_id.street,
                'street2': employee.address_id.street2,
                'city': employee.address_id.city,
                'zip': employee.address_id.zip,
                'neighborhood': employee.portal_neighborhood,
            },
            'brand': {
                'name': company.name,
                'logo': company.logo_web or company.logo,
                'primary_color': company.primary_color,
                'secondary_color': company.secondary_color,
                'website_id': company.website_id.id,
            },
        }

    def _owned_payslip_or_not_found(self, employee, payslip_id):
        payslip = request.env['hr.payslip'].sudo().search([
            ('id', '=', payslip_id), ('employee_id', '=', employee.id),
            ('company_id', '=', employee.company_id.id),
        ], limit=1)
        if not payslip or not payslip._portal_is_published():
            return None
        return payslip

    def _owned_issuance_or_not_found(self, employee, issuance_id):
        issuance = request.env['l10n_co.portal.employee.certificate.issuance'].sudo().search([
            ('id', '=', issuance_id), ('employee_id', '=', employee.id),
            ('requesting_user_id', '=', request.env.user.id),
            ('company_id', '=', employee.company_id.id),
        ], limit=1)
        return issuance or None

    @http.route(['/my/employee', '/my/employee/<int:employee_id>'], type='http', auth='user', website=True)
    def employee_dashboard(self, employee_id=None, **kwargs):
        employee = self._employee_or_not_found()
        if not employee or (employee_id and employee_id != employee.id):
            return request.not_found()
        return request.render('l10n_co_portal_empleado.portal_employee_dashboard', self._portal_values(employee))

    @http.route(['/my/employee/profile', '/my/employee/<int:employee_id>/profile'], type='http', auth='user', website=True)
    def employee_profile(self, employee_id=None, **kwargs):
        employee = self._employee_or_not_found()
        if not employee or (employee_id and employee_id != employee.id):
            return request.not_found()
        return request.render('l10n_co_portal_empleado.portal_employee_profile', self._portal_values(employee))

    @http.route('/my/employee/update', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def employee_update(self, **post):
        employee = self._employee_or_not_found()
        if not employee:
            return request.not_found()
        values = self._portal_values(employee)
        if request.httprequest.method == 'POST':
            allowed = request.env['l10n_co.portal.employee.update.request']._ALLOWED_VALUES
            try:
                unexpected = set(post) - allowed - {'csrf_token'}
                if unexpected:
                    raise ValidationError('Campos no permitidos en la solicitud.')
                proposed = {field: post[field].strip() for field in allowed if field in post and isinstance(post[field], str)}
                request.env['l10n_co.portal.employee.update.request'].create_from_portal(
                    employee, proposed, request.env.user)
            except (AccessError, ValidationError, ValueError, TypeError):
                values['error'] = 'No fue posible registrar la solicitud.'
            else:
                return request.redirect('/my/employee?update=sent')
        return request.render('l10n_co_portal_empleado.portal_employee_update', values)

    @http.route('/my/employee/payslips', type='http', auth='user', website=True)
    def employee_payslips(self, **kwargs):
        employee = self._employee_or_not_found()
        if not employee:
            return request.not_found()
        payslips = request.env['hr.payslip'].sudo().search([
            ('employee_id', '=', employee.id), ('company_id', '=', employee.company_id.id),
            ('state', 'in', ('done', 'paid')),
        ], order='date_to desc, id desc').filtered('_portal_is_published')
        values = self._portal_values(employee)
        values['payslips'] = [payslip._portal_dto() for payslip in payslips]
        return request.render('l10n_co_portal_empleado.portal_employee_payslips', values)

    @http.route('/my/employee/payslips/<int:payslip_id>/download', type='http', auth='user', website=True)
    def employee_payslip_download(self, payslip_id, **kwargs):
        employee = self._employee_or_not_found()
        payslip = employee and self._owned_payslip_or_not_found(employee, payslip_id)
        if not payslip:
            return request.not_found()
        try:
            pdf = payslip._portal_pdf()
        except (AccessError, ValidationError):
            return request.not_found()
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'attachment; filename="payslip.pdf"'),
        ])

    def _certificate_values(self, employee):
        issuances = request.env['l10n_co.portal.employee.certificate.issuance'].sudo().search([
            ('employee_id', '=', employee.id), ('requesting_user_id', '=', request.env.user.id),
            ('company_id', '=', employee.company_id.id),
        ], order='issued_at desc, id desc')
        values = self._portal_values(employee)
        values['issuances'] = [{
            'id': issuance.id, 'name': issuance.name, 'type': issuance.certificate_type,
            'issued_at': issuance.issued_at,
        } for issuance in issuances]
        return values

    @http.route('/my/employee/certificates', type='http', auth='user', website=True)
    def employee_certificates(self, **kwargs):
        employee = self._employee_or_not_found()
        if not employee:
            return request.not_found()
        return request.render('l10n_co_portal_empleado.portal_employee_certificates', self._certificate_values(employee))

    @http.route('/my/employee/certificates/without-salary', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def employee_certificate_without_salary(self, **post):
        return self._issue_certificate('without_salary', post)

    @http.route('/my/employee/certificates/with-salary', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def employee_certificate_with_salary(self, **post):
        return self._issue_certificate('with_salary', post)

    def _issue_certificate(self, certificate_type, post):
        employee = self._employee_or_not_found()
        if not employee:
            return request.not_found()
        values = self._certificate_values(employee)
        if set(post) - {'csrf_token'}:
            values['error'] = 'No fue posible emitir el certificado.'
            return request.render('l10n_co_portal_empleado.portal_employee_certificates', values)
        try:
            request.env['l10n_co.portal.employee.certificate.issuance'].create_from_portal(
                employee, certificate_type, request.env.user)
        except (AccessError, UserError, ValidationError):
            values['error'] = 'No fue posible emitir el certificado.'
            return request.render('l10n_co_portal_empleado.portal_employee_certificates', values)
        return request.redirect('/my/employee/certificates?issued=1')

    @http.route('/my/employee/certificates/<int:issuance_id>/download', type='http', auth='user', website=True)
    def employee_certificate_download(self, issuance_id, **kwargs):
        employee = self._employee_or_not_found()
        issuance = employee and self._owned_issuance_or_not_found(employee, issuance_id)
        if not issuance or not issuance.attachment_id:
            return request.not_found()
        pdf = base64.b64decode(issuance.attachment_id.sudo().datas or b'')
        if not pdf:
            return request.not_found()
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'attachment; filename="%s.pdf"' % issuance.name),
        ])
