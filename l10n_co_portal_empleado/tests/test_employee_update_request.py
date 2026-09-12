from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


def _employee_values(env, values):
    """Keep F1 tests installable with or without the NE localization."""
    if 'l10n_co_ne_payment_method' in env['hr.employee']._fields:
        values['l10n_co_ne_payment_method'] = '10'
    return values


class TestEmployeeUpdateRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal Employee', 'login': 'portal.employee@test.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.employee = cls.env['hr.employee'].create(_employee_values(cls.env, {
            'name': 'Portal Employee', 'company_id': cls.company.id, 'user_id': cls.portal_user.id,
        }))
        cls.hr_manager = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'HR Manager', 'login': 'hr.manager@test.invalid',
            'groups_id': [(6, 0, [cls.env.ref('hr.group_hr_manager').id])],
        })

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
        other_company = self.env['res.company'].create({'name': 'Other company'})
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
        other_company = self.env['res.company'].create({'name': 'Blocked company'})
        blocked_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Blocked Portal', 'login': 'blocked.portal@test.invalid',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
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
