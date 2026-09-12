from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import TransactionCase


def _employee_values(env, values):
    """Keep F1 tests installable with or without the NE localization."""
    if 'l10n_co_ne_payment_method' in env['hr.employee']._fields:
        values['l10n_co_ne_payment_method'] = '10'
    return values


def _user_values(env, values):
    """Reuse a compliant partner where Guapante requires a fiscal regime."""
    values = dict(values)
    partner_model = env['res.partner']
    field = partner_model._fields.get('l10n_co_edi_fiscal_regimen')
    if field:
        partner = partner_model.search([('l10n_co_edi_fiscal_regimen', '!=', False)], limit=1)
        if not partner:
            selection = field._description_selection(env)
            partner = partner_model.create({
                'name': '%s Partner' % values['name'],
                'l10n_co_edi_fiscal_regimen': selection[0][0],
            })
        values['partner_id'] = partner.id
    return values


class TestPortalEmployeeIdentity(TransactionCase):
    def setUp(self):
        super().setUp()
        self.user = self.env['res.users'].with_context(no_reset_password=True).create(_user_values(self.env, {
            'name': 'Portal A', 'login': 'portal.a@test.invalid',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        }))
        self.employee = self.env['hr.employee'].create(
            _employee_values(self.env, {'name': 'A', 'user_id': self.user.id}))

    def test_unique_active_link_is_required(self):
        model = self.env['l10n_co.portal.employee.update.request'].with_user(self.user)
        self.assertEqual(model._unique_employee_for_user(self.user), self.employee)
        self.env['hr.employee'].create(
            _employee_values(self.env, {'name': 'Duplicate', 'user_id': self.user.id}))
        with self.assertRaises(AccessError):
            model._unique_employee_for_user(self.user)

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
        cls.user_a = cls.env['res.users'].with_context(no_reset_password=True).create(_user_values(cls.env, {
            'name': 'Portal A', 'login': 'portal.route.a@test.invalid', 'password': 'portal-route-a',
            'groups_id': [(6, 0, [group.id])],
        }))
        cls.user_without_link = cls.env['res.users'].with_context(no_reset_password=True).create(_user_values(cls.env, {
            'name': 'No Link', 'login': 'portal.no.link@test.invalid', 'password': 'portal-no-link',
            'groups_id': [(6, 0, [group.id])],
        }))
        cls.company_b = cls.env['res.company'].create({'name': 'Company B Portal'})
        cls.user_b = cls.env['res.users'].with_context(no_reset_password=True).create(_user_values(cls.env, {
            'name': 'Portal B', 'login': 'portal.route.b@test.invalid', 'password': 'portal-route-b',
            'company_id': cls.company_b.id, 'company_ids': [(6, 0, [cls.company_b.id])],
            'groups_id': [(6, 0, [group.id])],
        }))
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
