from odoo import http
from odoo.exceptions import AccessError, ValidationError
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
