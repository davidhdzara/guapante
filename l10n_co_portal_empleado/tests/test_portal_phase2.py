import base64
from datetime import date
from unittest import SkipTest
from unittest.mock import patch
from uuid import uuid4

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import TransactionCase


def _employee_values(env, values):
    if 'l10n_co_ne_payment_method' in env['hr.employee']._fields:
        values['l10n_co_ne_payment_method'] = '10'
    return values


def _portal_user(env, label):
    """Use an explicit partner to avoid the automatic partner DB constraint."""
    partner_values = {'name': label}
    if 'l10n_co_edi_fiscal_regimen' in env['res.partner']._fields:
        partner_values['l10n_co_edi_fiscal_regimen'] = '48'
    partner = env['res.partner'].create(partner_values)
    group = env.ref('base.group_portal')
    return env['res.users'].with_context(no_reset_password=True).create({
        'name': label, 'login': 'portal-phase2-%s@test.invalid' % uuid4().hex,
        'password': 'portal-phase2', 'partner_id': partner.id,
        'groups_id': [(6, 0, [group.id])],
    })


def _signatory(company):
    company.write({
        'l10n_co_portal_certificate_signatory_name': 'Responsable RRHH',
        'l10n_co_portal_certificate_signatory_title': 'Dirección de RRHH',
        'l10n_co_portal_certificate_signatory_signature': base64.b64encode(b'signature'),
    })


class TestPortalPhase2(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.portal_user = _portal_user(cls.env, 'Portal phase 2')
        cls.employee = cls.env['hr.employee'].create(_employee_values(cls.env, {
            'name': 'Portal certificate employee', 'user_id': cls.portal_user.id,
            'company_id': cls.company.id,
        }))

    def _issue(self, certificate_type='without_salary'):
        _signatory(self.company)
        model = self.env['l10n_co.portal.employee.certificate.issuance']
        with patch.object(type(self.env['ir.actions.report']), '_render_qweb_pdf', return_value=(b'%PDF-test', 'pdf')):
            return model.create_from_portal(self.employee, certificate_type, self.portal_user)

    def test_portal_cannot_search_read_or_create_issuance_by_orm(self):
        issuance = self._issue()
        model = self.env['l10n_co.portal.employee.certificate.issuance'].with_user(self.portal_user)
        with self.assertRaises(AccessError):
            model.search([])
        with self.assertRaises(AccessError):
            model.browse(issuance.id).read(['wage_snapshot', 'signatory_signature_snapshot'])
        with self.assertRaises(AccessError):
            model.create({})

    def test_missing_signatory_creates_no_issuance(self):
        self.company.write({
            'l10n_co_portal_certificate_signatory_name': False,
            'l10n_co_portal_certificate_signatory_title': False,
            'l10n_co_portal_certificate_signatory_signature': False,
        })
        model = self.env['l10n_co.portal.employee.certificate.issuance']
        before = model.search_count([])
        with self.assertRaises(UserError):
            model.create_from_portal(self.employee, 'without_salary', self.portal_user)
        self.assertEqual(model.search_count([]), before)

    def test_render_error_rolls_back_issuance_and_attachment(self):
        _signatory(self.company)
        model = self.env['l10n_co.portal.employee.certificate.issuance']
        before_issuance = model.search_count([])
        before_attachment = self.env['ir.attachment'].search_count([('res_model', '=', model._name)])
        with patch.object(type(self.env['ir.actions.report']), '_render_qweb_pdf', side_effect=UserError('render failed')):
            with self.assertRaises(UserError):
                model.create_from_portal(self.employee, 'without_salary', self.portal_user)
        self.assertEqual(model.search_count([]), before_issuance)
        self.assertEqual(self.env['ir.attachment'].search_count([('res_model', '=', model._name)]), before_attachment)

    def test_without_salary_never_looks_up_contract_or_persists_salary(self):
        _signatory(self.company)
        model = self.env['l10n_co.portal.employee.certificate.issuance']
        with patch.object(type(model), '_active_contract', side_effect=AssertionError('No debe consultar contrato')):
            with patch.object(type(self.env['ir.actions.report']), '_render_qweb_pdf', return_value=(b'%PDF-test', 'pdf')):
                issuance = model.create_from_portal(self.employee, 'without_salary', self.portal_user)
        self.assertFalse(issuance.wage_snapshot)
        self.assertFalse(issuance.currency_id)
        self.assertTrue(issuance.checksum_sha256)
        self.assertFalse(issuance.attachment_id.public)
        self.assertFalse(issuance.attachment_id.access_token)

    def test_with_salary_requires_one_open_contract_same_company(self):
        _signatory(self.company)
        model = self.env['l10n_co.portal.employee.certificate.issuance']
        with self.assertRaises(AccessError):
            model.create_from_portal(self.employee, 'with_salary', self.portal_user)
        structure_type = self.env['hr.payroll.structure.type'].search([('country_id', '=', self.company.country_id.id)], limit=1)
        if not structure_type:
            raise SkipTest('No hay tipo de estructura de nómina para crear contrato de prueba.')
        contract = self.env['hr.contract'].create({
            'name': 'Contrato F2', 'employee_id': self.employee.id, 'company_id': self.company.id,
            'structure_type_id': structure_type.id, 'date_start': date.today(), 'state': 'open', 'wage': 2500000,
        })
        with patch.object(type(self.env['ir.actions.report']), '_render_qweb_pdf', return_value=(b'%PDF-salary', 'pdf')):
            issuance = model.create_from_portal(self.employee, 'with_salary', self.portal_user)
        self.assertEqual(issuance.wage_snapshot, contract.wage)
        self.assertEqual(issuance.currency_id, contract.currency_id)
        contract.copy({'name': 'Contrato F2 duplicado', 'state': 'open'})
        with self.assertRaises(AccessError):
            model.create_from_portal(self.employee, 'with_salary', self.portal_user)

    def test_payslip_policy_acceptance_and_finalization(self):
        slip = self.env['hr.payslip'].new({'employee_id': self.employee.id, 'company_id': self.company.id})
        self.company.l10n_co_portal_payslip_publication_policy = 'accepted'
        for state in ('draft', 'verify', 'cancel'):
            slip.state, slip.l10n_co_ne_state = state, 'accepted'
            self.assertFalse(slip._portal_is_published())
        slip.state, slip.l10n_co_ne_state = 'done', 'rejected'
        self.assertFalse(slip._portal_is_published())
        slip.l10n_co_ne_state = 'accepted'
        self.assertTrue(slip._portal_is_published())
        self.company.l10n_co_portal_payslip_publication_policy = 'finalized'
        slip.state, slip.l10n_co_ne_state = 'done', 'rejected'
        self.assertTrue(slip._portal_is_published())

    def test_signatory_of_another_company_never_applies(self):
        other_company = self.env['res.company'].search([('id', '!=', self.company.id)], limit=1)
        if not other_company:
            raise SkipTest('La base de prueba no tiene una segunda compañía.')
        _signatory(other_company)
        self.company.write({
            'l10n_co_portal_certificate_signatory_name': False,
            'l10n_co_portal_certificate_signatory_title': False,
            'l10n_co_portal_certificate_signatory_signature': False,
        })
        with self.assertRaises(UserError):
            self.env['l10n_co.portal.employee.certificate.issuance'].create_from_portal(
                self.employee, 'without_salary', self.portal_user)

    def test_cross_company_issuance_is_prepared_for_multicompany_qa(self):
        other_company = self.env['res.company'].search([('id', '!=', self.company.id)], limit=1)
        if not other_company:
            raise SkipTest('QA multicompañía pendiente: la base tiene una sola compañía.')
        other_user = _portal_user(self.env, 'Portal phase 2 B')
        other_user.write({'company_id': other_company.id, 'company_ids': [(6, 0, [other_company.id])]})
        other_employee = self.env['hr.employee'].create(_employee_values(self.env, {
            'name': 'Portal certificate employee B', 'user_id': other_user.id,
            'company_id': other_company.id,
        }))
        with self.assertRaises(AccessError):
            self.env['l10n_co.portal.employee.certificate.issuance'].create_from_portal(
                other_employee, 'without_salary', self.portal_user)


@tagged('-at_install', 'post_install')
class TestPortalPhase2Routes(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.portal_user = _portal_user(cls.env, 'Portal phase 2 HTTP')
        cls.employee = cls.env['hr.employee'].create(_employee_values(cls.env, {
            'name': 'Portal certificate HTTP', 'user_id': cls.portal_user.id,
            'company_id': cls.company.id,
        }))
        _signatory(cls.company)
        model = cls.env['l10n_co.portal.employee.certificate.issuance']
        with patch.object(type(cls.env['ir.actions.report']), '_render_qweb_pdf', return_value=(b'%PDF-route', 'pdf')):
            cls.issuance = model.create_from_portal(cls.employee, 'without_salary', cls.portal_user)

    def test_controller_history_and_private_download_work_without_orm_acl(self):
        self.authenticate(self.portal_user.login, 'portal-phase2')
        self.assertEqual(self.url_open('/my/employee/certificates').status_code, 200)
        response = self.url_open('/my/employee/certificates/%s/download' % self.issuance.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'application/pdf')

    def test_generic_report_and_attachment_routes_are_denied(self):
        self.authenticate(self.portal_user.login, 'portal-phase2')
        report = self.url_open('/report/pdf/l10n_co_portal_empleado.report_employee_certificate/%s' % self.issuance.id)
        attachment = self.url_open('/web/content/%s' % self.issuance.attachment_id.id)
        self.assertIn(report.status_code, (403, 404))
        self.assertIn(attachment.status_code, (403, 404))
