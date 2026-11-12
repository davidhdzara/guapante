# -*- coding: utf-8 -*-
"""Aislamiento multiempresa de los modelos propios con company_id (doc 51, M4 paso 2).

Companias A y B colombianas y M mexicana. Usuario solo-A, usuario solo-B y usuario multiempresa
(A, B, M). Cada usuario ve unicamente los registros de las companias que tiene activas; la
configuracion de retencion COMPARTIDA (company_id vacio) la ven todos.
"""

from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

MODELOS_CON_REGLA = (
    'l10n.co.retefuente.uvt', 'l10n.co.retefuente.procedure2', 'l10n.co.ibc.mensual',
    'l10n_co_nomina.ugpp', 'l10n.co.pila.planilla', 'l10n.co.payslip.tercero',
    'l10n.co.ne.operation_mode')


@tagged('post_install', '-at_install')
class TestMultiempresaAislamiento(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        datos = {'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
                 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.a = Company.create({'name': 'Empresa A Aislamiento',
                                'country_id': cls.env.ref('base.co').id, **datos})
        cls.b = Company.create({'name': 'Empresa B Aislamiento',
                                'country_id': cls.env.ref('base.co').id, **datos})
        cls.m = Company.create({'name': 'Empresa M Aislamiento',
                                'country_id': cls.env.ref('base.mx').id})
        grupos = [cls.env.ref('base.group_user').id,
                  cls.env.ref('hr_payroll.group_hr_payroll_manager').id]

        def usuario(login, companias):
            return cls.env['res.users'].create({
                'name': login, 'login': login, 'company_id': companias[0].id,
                'company_ids': [(6, 0, companias.ids)], 'groups_id': [(6, 0, grupos)]})

        cls.user_a = usuario('aislamiento_a', cls.a)
        cls.user_b = usuario('aislamiento_b', cls.b)
        cls.user_multi = usuario('aislamiento_multi', cls.a | cls.b | cls.m)

        Ibc, Planilla, Config = (cls.env['l10n.co.ibc.mensual'], cls.env['l10n.co.pila.planilla'],
                                 cls.env['l10n.co.retefuente.uvt'])
        cls.ibc, cls.planilla, cls.config = {}, {}, {}
        for clave, company in (('a', cls.a), ('b', cls.b)):
            empleado = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
                'name': 'Emp %s' % clave, 'company_id': company.id})
            cls.ibc[clave] = Ibc.create({
                'company_id': company.id, 'employee_id': empleado.id,
                'period': date(2026, 3, 1)})
            cls.planilla[clave] = Planilla.create({
                'company_id': company.id, 'period': date(2026, 3, 1), 'tipo_planilla': 'E',
                'operador_code': 'X'})
            cls.config[clave] = Config.create({
                'year': '2028', 'company_id': company.id, 'procedure': '1'})
        cls.config['compartida'] = Config.create({
            'year': '2029', 'company_id': False, 'procedure': '1'})

    def _ver(self, modelo, user, companias=None):
        ctx = {'allowed_company_ids': (companias or user.company_ids).ids}
        return self.env[modelo].with_user(user).with_context(**ctx)

    def test_cada_modelo_propio_tiene_su_regla_por_compania(self):
        for modelo in MODELOS_CON_REGLA:
            reglas = self.env['ir.rule'].sudo().search([
                ('model_id.model', '=', modelo), ('global', '=', True)])
            self.assertTrue(
                any('company_ids' in (r.domain_force or '') for r in reglas), modelo)

    def test_a_no_ve_lo_de_b_y_viceversa(self):
        self.assertEqual(self._ver('l10n.co.ibc.mensual', self.user_a).search(
            [('id', 'in', [self.ibc['a'].id, self.ibc['b'].id])]), self.ibc['a'])
        self.assertEqual(self._ver('l10n.co.ibc.mensual', self.user_b).search(
            [('id', 'in', [self.ibc['a'].id, self.ibc['b'].id])]), self.ibc['b'])
        self.assertEqual(self._ver('l10n.co.pila.planilla', self.user_a).search(
            [('id', 'in', [self.planilla['a'].id, self.planilla['b'].id])]), self.planilla['a'])

    def test_el_usuario_multiempresa_ve_las_de_sus_companias_activas(self):
        ids = [self.ibc['a'].id, self.ibc['b'].id]
        todas = self._ver('l10n.co.ibc.mensual', self.user_multi).search([('id', 'in', ids)])
        self.assertEqual(todas, self.ibc['a'] | self.ibc['b'])
        solo_a = self._ver('l10n.co.ibc.mensual', self.user_multi, self.a).search(
            [('id', 'in', ids)])
        self.assertEqual(solo_a, self.ibc['a'])

    def test_la_configuracion_compartida_la_ven_todos_la_propia_solo_su_compania(self):
        ids = [c.id for c in self.config.values()]
        ve_a = self._ver('l10n.co.retefuente.uvt', self.user_a).search([('id', 'in', ids)])
        self.assertEqual(ve_a, self.config['a'] | self.config['compartida'])
        ve_b = self._ver('l10n.co.retefuente.uvt', self.user_b).search([('id', 'in', ids)])
        self.assertEqual(ve_b, self.config['b'] | self.config['compartida'])

    def test_no_se_puede_mezclar_companias_en_un_ibc_mensual(self):
        """_check_company_auto: un consolidado de A no puede apuntar a un empleado de B."""
        empleado_b = self.ibc['b'].employee_id
        with self.assertRaises(UserError):
            self.ibc['a'].employee_id = empleado_b

    def test_el_usuario_de_a_no_puede_leer_la_planilla_de_b(self):
        with self.assertRaises(AccessError):
            self.planilla['b'].with_user(self.user_a).with_context(
                allowed_company_ids=self.user_a.company_ids.ids).read(['period'])
