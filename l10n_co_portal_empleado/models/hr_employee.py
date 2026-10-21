from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    portal_neighborhood = fields.Char(string='Barrio')
    portal_emergency_relationship = fields.Char(string='Parentesco contacto de emergencia')
    portal_access_state = fields.Selection(
        [('no_user', 'Sin usuario'), ('portal', 'Usuario portal'), ('internal', 'Usuario interno')],
        compute='_compute_portal_access_state', string='Estado Portal',
    )
    portal_update_request_ids = fields.One2many(
        'l10n_co.portal.employee.update.request', 'employee_id',
        string='Solicitudes de actualización portal',
    )
    portal_update_request_count = fields.Integer(compute='_compute_portal_update_request_count')

    @api.depends('user_id', 'user_id.groups_id')
    def _compute_portal_access_state(self):
        for employee in self:
            if not employee.user_id:
                employee.portal_access_state = 'no_user'
            elif employee.user_id.has_group('base.group_user'):
                employee.portal_access_state = 'internal'
            elif employee.user_id.has_group('base.group_portal'):
                employee.portal_access_state = 'portal'
            else:
                employee.portal_access_state = 'no_user'

    def _compute_portal_update_request_count(self):
        grouped = self.env['l10n_co.portal.employee.update.request'].read_group(
            [('employee_id', 'in', self.ids)], ['employee_id'], ['employee_id'])
        counts = {item['employee_id'][0]: item['employee_id_count'] for item in grouped}
        for employee in self:
            employee.portal_update_request_count = counts.get(employee.id, 0)

    def action_open_portal_update_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Solicitudes de actualización portal',
            'res_model': 'l10n_co.portal.employee.update.request',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
