from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase
from unittest import SkipTest


def _employee_values(env, values):
    """Keep F1 tests installable with or without the NE localization."""
    if 'l10n_co_ne_payment_method' in env['hr.employee']._fields:
        values['l10n_co_ne_payment_method'] = '10'
    return values


def _portal_users_without_employee(env, count):
    portal_group = env.ref('base.group_portal')
    candidates = env['res.users'].with_context(active_test=False).search([
        ('groups_id', 'in', [portal_group.id])], order='id')
    user_ids_with_employee = set(env['hr.employee'].sudo().search([
        ('active', '=', True), ('user_id', '!=', False)]).mapped('user_id').ids)
    users = candidates.filtered(lambda user: user.id not in user_ids_with_employee)
    if len(users) < count:
        raise AssertionError('Se requieren usuarios Portal sin empleado activo para la prueba.')
    return users[:count]


def _prepare_hr_manager(user):
    user.write({'groups_id': [(4, user.env.ref('hr.group_hr_manager').id)]})
    return user


def _other_company(env):
    company = env['res.company'].search([('id', '!=', env.company.id)], limit=1)
    if not company:
        raise SkipTest('La base de prueba no tiene una segunda compañía.')
    return company


class TestEmployeeUpdateRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.portal_user = _portal_users_without_employee(cls.env, 1)
        cls.employee = cls.env['hr.employee'].create(_employee_values(cls.env, {
            'name': 'Portal Employee', 'company_id': cls.company.id, 'user_id': cls.portal_user.id,
        }))
        cls.hr_manager = _prepare_hr_manager(cls.env.ref('base.user_admin'))

    def test_allowlist_rejects_payroll_company_and_work_email(self):
        model = self.env['l10n_co.portal.employee.update.request']
        for forbidden in ('wage', 'contract_id', 'work_email', 'company_id'):
            with self.assertRaises(ValidationError):
                model.create_from_portal(self.employee, {forbidden: 'blocked'}, self.portal_user)

    def test_portal_orm_create_is_denied_even_for_own_employee(self):
        with self.assertRaises(AccessError):
            self.env['l10n_co.portal.employee.update.request'].with_user(self.portal_user).create({
                'company_id': self.company.id,
                'employee_id': self.employee.id,
                'requesting_user_id': self.portal_user.id,
                'state': 'submitted',
            })

    def test_create_rejects_company_different_from_linked_employee(self):
        other_company = _other_company(self.env)
        with self.assertRaises(AccessError):
            self.env['l10n_co.portal.employee.update.request'].with_user(self.portal_user).create({
                'company_id': other_company.id,
                'employee_id': self.employee.id,
                'requesting_user_id': self.portal_user.id,
                'state': 'submitted',
            })

    def test_approval_updates_only_allowed_snapshot(self):
        request = self.env['l10n_co.portal.employee.update.request'].create_from_portal(
            self.employee, {'private_email': 'new.personal@test.invalid', 'mobile_phone': '3000000000'}, self.portal_user)
        manager = self.hr_manager
        request.with_user(manager).action_approve()
        self.assertEqual(self.employee.private_email, 'new.personal@test.invalid')
        self.assertEqual(self.employee.mobile_phone, '3000000000')
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.approver_id, manager)
        self.assertTrue(request.resolution_date)

    def test_employee_from_unauthorized_company_is_blocked(self):
        other_company = _other_company(self.env)
        blocked_user = _portal_users_without_employee(self.env, 2)[1]
        blocked_employee = self.env['hr.employee'].create(_employee_values(self.env, {
            'name': 'Blocked employee', 'user_id': blocked_user.id, 'company_id': other_company.id,
        }))
        model = self.env['l10n_co.portal.employee.update.request'].with_user(blocked_user)
        with self.assertRaises(AccessError):
            model._unique_employee_for_user(blocked_user)
        with self.assertRaises(AccessError):
            model.create_from_portal(blocked_employee, {'private_phone': '3000000000'}, blocked_user)

    def test_rejection_keeps_audit_data(self):
        request = self.env['l10n_co.portal.employee.update.request'].create_from_portal(
            self.employee, {'private_phone': '3000000000'}, self.portal_user)
        request.with_user(self.hr_manager).write({'rejection_reason': 'Soporte incompleto'})
        request.with_user(self.hr_manager).action_reject()
        self.assertEqual(request.state, 'rejected')
        self.assertEqual(request.rejection_reason, 'Soporte incompleto')
        self.assertTrue(request.resolution_date)
