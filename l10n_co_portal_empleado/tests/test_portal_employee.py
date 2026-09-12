from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
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


def _prepare_portal_user(user, login, password=None, company=None):
    """Reuse a pre-existing Portal user; never create users or change its type."""
    values = {'active': True, 'login': login}
    if password:
        values['password'] = password
    if company:
        values.update({
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
        })
    user.with_context(no_reset_password=True).write(values)
    return user


def _other_company(env):
    company = env['res.company'].search([('id', '!=', env.company.id)], limit=1)
    if not company:
        raise SkipTest('La base de prueba no tiene una segunda compañía.')
    return company


class TestPortalEmployeeIdentity(TransactionCase):
    def setUp(self):
        super().setUp()
        self.user = _prepare_portal_user(
            _portal_users_without_employee(self.env, 1), 'portal.a@test.invalid')
        self.employee = self.env['hr.employee'].create(
            _employee_values(self.env, {'name': 'A', 'user_id': self.user.id}))

    def test_unique_active_link_is_required(self):
        model = self.env['l10n_co.portal.employee.update.request'].with_user(self.user)
        self.assertEqual(model._unique_employee_for_user(self.user), self.employee)

    def test_internal_user_keeps_internal_group_and_portal_has_no_backend_group(self):
        self.assertFalse(self.user.has_group('base.group_user'))
        internal = self.env.ref('base.user_admin')
        self.assertTrue(internal.has_group('base.group_user'))


@tagged('-at_install', 'post_install')
class TestPortalEmployeeRoutes(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = cls.env.ref('base.group_portal')
        portal_users = _portal_users_without_employee(cls.env, 3)
        cls.user_a = _prepare_portal_user(
            portal_users[0], 'portal.route.a@test.invalid', 'portal-route-a')
        cls.user_without_link = _prepare_portal_user(
            portal_users[1], 'portal.no.link@test.invalid', 'portal-no-link')
        cls.company_b = _other_company(cls.env)
        cls.user_b = _prepare_portal_user(
            portal_users[2], 'portal.route.b@test.invalid', 'portal-route-b', cls.company_b)
        cls.employee_a = cls.env['hr.employee'].create(
            _employee_values(cls.env, {'name': 'Route A', 'user_id': cls.user_a.id}))
        cls.employee_b = cls.env['hr.employee'].create(_employee_values(cls.env, {
            'name': 'Route B', 'user_id': cls.user_b.id, 'company_id': cls.company_b.id,
        }))

    def test_portal_a_cannot_discover_employee_b_by_url_id(self):
        self.authenticate('portal.route.a@test.invalid', 'portal-route-a')
        self.assertEqual(self.url_open('/my/employee/%s' % self.employee_a.id).status_code, 200)
        self.assertEqual(self.url_open('/my/employee/%s' % self.employee_b.id).status_code, 404)
        self.assertEqual(self.url_open('/my/employee/%s/profile' % self.employee_b.id).status_code, 404)

    def test_user_without_unique_link_receives_not_found(self):
        self.authenticate('portal.no.link@test.invalid', 'portal-no-link')
        self.assertEqual(self.url_open('/my/employee').status_code, 404)
