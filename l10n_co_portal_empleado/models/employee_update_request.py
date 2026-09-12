from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class EmployeeUpdateRequest(models.Model):
    _name = 'l10n_co.portal.employee.update.request'
    _description = 'Solicitud de actualización de datos de empleado desde Portal'
    _order = 'request_date desc, id desc'

    _ALLOWED_VALUES = {
        'private_email', 'private_phone', 'mobile_phone', 'emergency_contact',
        'emergency_phone', 'portal_emergency_relationship', 'street', 'street2',
        'city', 'zip', 'state_id', 'country_id', 'portal_neighborhood',
    }

    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    employee_id = fields.Many2one('hr.employee', required=True, readonly=True, index=True, ondelete='restrict')
    requesting_user_id = fields.Many2one('res.users', required=True, readonly=True, index=True)
    state = fields.Selection([
        ('draft', 'Borrador'), ('submitted', 'Enviada'), ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'), ('cancelled', 'Cancelada'),
    ], required=True, default='draft', readonly=True, index=True)
    request_date = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    resolution_date = fields.Datetime(readonly=True)
    approver_id = fields.Many2one('res.users', readonly=True)
    rejection_reason = fields.Text(readonly=True)

    old_private_email = fields.Char(readonly=True); proposed_private_email = fields.Char(readonly=True)
    old_private_phone = fields.Char(readonly=True); proposed_private_phone = fields.Char(readonly=True)
    old_mobile_phone = fields.Char(readonly=True); proposed_mobile_phone = fields.Char(readonly=True)
    old_emergency_contact = fields.Char(readonly=True); proposed_emergency_contact = fields.Char(readonly=True)
    old_emergency_phone = fields.Char(readonly=True); proposed_emergency_phone = fields.Char(readonly=True)
    old_portal_emergency_relationship = fields.Char(readonly=True); proposed_portal_emergency_relationship = fields.Char(readonly=True)
    old_street = fields.Char(readonly=True); proposed_street = fields.Char(readonly=True)
    old_street2 = fields.Char(readonly=True); proposed_street2 = fields.Char(readonly=True)
    old_city = fields.Char(readonly=True); proposed_city = fields.Char(readonly=True)
    old_zip = fields.Char(readonly=True); proposed_zip = fields.Char(readonly=True)
    old_state_id = fields.Many2one('res.country.state', readonly=True); proposed_state_id = fields.Many2one('res.country.state', readonly=True)
    old_country_id = fields.Many2one('res.country', readonly=True); proposed_country_id = fields.Many2one('res.country', readonly=True)
    old_portal_neighborhood = fields.Char(readonly=True); proposed_portal_neighborhood = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            invalid = set(vals) - self._create_fields()
            if invalid:
                raise ValidationError(_('Campos no permitidos en una solicitud: %s') % ', '.join(sorted(invalid)))
            if not self.env.su:
                employee = self._unique_employee_for_user(self.env.user)
                if (vals.get('employee_id') != employee.id
                        or vals.get('requesting_user_id') != self.env.user.id
                        or vals.get('company_id') != employee.company_id.id):
                    raise AccessError(_('Solo puede crear solicitudes para su propio empleado.'))
        return super().create(vals_list)

    @api.model
    def _create_fields(self):
        return {'company_id', 'employee_id', 'requesting_user_id', 'state', 'request_date'} | {
            prefix + field for prefix in ('old_', 'proposed_') for field in self._ALLOWED_VALUES}

    @api.model
    def _unique_employee_for_user(self, user):
        allowed_companies = user.company_ids & self.env.companies
        employees = self.env['hr.employee'].sudo().search([
            ('user_id', '=', user.id), ('active', '=', True),
            ('company_id', 'in', allowed_companies.ids)], limit=2)
        if len(employees) != 1:
            raise AccessError(_('No existe un vínculo único de empleado activo para este usuario.'))
        return employees

    @api.model
    def create_from_portal(self, employee, proposed_values, user=None):
        """Trusted boundary used by controllers after identity validation."""
        user = user or self.env.user
        allowed_companies = user.company_ids & self.env.companies
        if (employee.user_id != user or not employee.active
                or employee.company_id not in allowed_companies):
            raise AccessError(_('El empleado no pertenece al usuario autenticado.'))
        unexpected = set(proposed_values) - self._ALLOWED_VALUES
        if unexpected:
            raise ValidationError(_('Intento de actualizar campos no permitidos: %s') % ', '.join(sorted(unexpected)))
        address = employee.address_id.sudo()
        vals = {
            'company_id': employee.company_id.id,
            'employee_id': employee.id,
            'requesting_user_id': user.id,
            'state': 'submitted',
        }
        for field in self._ALLOWED_VALUES:
            source = address if field in {'street', 'street2', 'city', 'zip', 'state_id', 'country_id'} else employee
            old_value = source[field]
            vals['old_%s' % field] = old_value.id if hasattr(old_value, 'id') else old_value
            value = proposed_values.get(field, old_value)
            vals['proposed_%s' % field] = value.id if hasattr(value, 'id') else value
        return self.sudo().create(vals)

    def _assert_pending(self):
        if any(record.state != 'submitted' for record in self):
            raise UserError(_('Solo se pueden resolver solicitudes enviadas.'))

    def action_approve(self):
        if not self.env.user.has_group('hr.group_hr_manager'):
            raise AccessError(_('Solo un responsable de RR. HH. puede aprobar solicitudes.'))
        self._assert_pending()
        for record in self:
            employee = record.employee_id.sudo()
            employee_values, address_values = {}, {}
            for field in self._ALLOWED_VALUES:
                value = record['proposed_%s' % field]
                target = address_values if field in {'street', 'street2', 'city', 'zip', 'state_id', 'country_id'} else employee_values
                target[field] = value.id if hasattr(value, 'id') else value
            employee.write(employee_values)
            if address_values:
                if not employee.address_id:
                    address = self.env['res.partner'].sudo().create({
                        'name': employee.name,
                        'company_id': employee.company_id.id,
                        **address_values,
                    })
                    employee.write({'address_id': address.id})
                else:
                    employee.address_id.sudo().write(address_values)
            record.sudo().write({
                'state': 'approved', 'approver_id': self.env.user.id,
                'resolution_date': fields.Datetime.now(),
            })
        return True

    def action_reject(self):
        if not self.env.user.has_group('hr.group_hr_manager'):
            raise AccessError(_('Solo un responsable de RR. HH. puede rechazar solicitudes.'))
        self._assert_pending()
        if any(not record.rejection_reason for record in self):
            raise UserError(_('Debe indicar el motivo de rechazo.'))
        self.sudo().write({
            'state': 'rejected', 'approver_id': self.env.user.id,
            'resolution_date': fields.Datetime.now(),
        })
        return True

    def write(self, vals):
        protected = self._create_fields() | {'resolution_date', 'approver_id', 'rejection_reason'}
        if set(vals) & protected and not self.env.su and not self.env.user.has_group('hr.group_hr_manager'):
            raise AccessError(_('Las solicitudes enviadas no pueden ser modificadas por Portal.'))
        return super().write(vals)
