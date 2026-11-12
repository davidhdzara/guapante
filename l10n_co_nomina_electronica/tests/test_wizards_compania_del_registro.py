# -*- coding: utf-8 -*-
"""Los asistentes y el calculo del recibo trabajan con la compania del registro, no con la activa
en el selector (doc 51, M4 paso 2, .178). Companias A y B colombianas y M mexicana."""

from datetime import date
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWizardsCompaniaDelRegistro(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        datos = {'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
                 'l10n_co_ne_redondeo_dias': 'DOWN'}
        cls.a = Company.create({'name': 'Empresa A Wizards',
                                'country_id': cls.env.ref('base.co').id, **datos})
        cls.b = Company.create({'name': 'Empresa B Wizards',
                                'country_id': cls.env.ref('base.co').id, **datos})
        cls.m = Company.create({'name': 'Empresa M Wizards',
                                'country_id': cls.env.ref('base.mx').id})
        cls.tipo = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Wizards', 'country_id': cls.env.ref('base.co').id})
        cls.est = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_prima')

    def test_ugpp_genera_el_reporte_de_la_compania_elegida_no_de_la_activa(self):
        activa = self.env.company
        wizard = self.env['l10n_co_nomina.ugpp.wizard'].create({
            'company_id': self.b.id, 'year': 2026, 'month': '3'})
        with mock.patch.object(
                self.env.registry['l10n_co_nomina.ugpp'], 'action_generate_report',
                autospec=True, return_value=True):
            accion = wizard.action_generate()
        reporte = self.env['l10n_co_nomina.ugpp'].browse(accion['res_id'])
        self.assertEqual(reporte.company_id, self.b)
        self.assertNotEqual(reporte.company_id, activa)
        self.assertEqual(str(reporte.date_from), '2026-03-01')
        self.assertEqual(str(reporte.date_to), '2026-03-31')

    def test_ugpp_con_compania_mexicana_falla_nombrandola(self):
        wizard = self.env['l10n_co_nomina.ugpp.wizard'].create({
            'company_id': self.m.id, 'year': 2026, 'month': '3'})
        with self.assertRaises(UserError) as exc:
            wizard.action_generate()
        self.assertIn('Empresa M Wizards', str(exc.exception))

    def test_pila_y_habilitacion_no_se_crean_para_una_compania_mexicana(self):
        for modelo in ('l10n.co.hr.pila.wizard.v2', 'l10n.co.ne.certification.wizard'):
            with self.assertRaises(UserError) as exc:
                self.env[modelo].create({'company_id': self.m.id})
            self.assertIn('Empresa M Wizards', str(exc.exception), modelo)
        self.assertTrue(self.env['l10n.co.hr.pila.wizard.v2'].create({'company_id': self.a.id}))

    def test_consulta_por_cune_usa_la_compania_del_documento(self):
        """Sin documento para ese CUNE en las companias autorizadas: error claro; no se filtra por
        la compania activa."""
        wizard = self.env['l10n.co.ne.status.cune.wizard'].create({'cune': 'NO-EXISTE'})
        with self.assertRaises(UserError) as exc:
            wizard._resolve_payslip()
        self.assertIn('sus compañías', str(exc.exception))

    def test_compute_sheet_corre_en_el_contexto_de_la_compania_de_cada_recibo(self):
        def recibo(company):
            empleado = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
                'name': 'Emp %s' % company.name, 'company_id': company.id})
            contrato = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
                'name': 'C', 'employee_id': empleado.id, 'company_id': company.id,
                'structure_type_id': self.tipo.id, 'wage': 1000000.0,
                'date_start': date(2026, 1, 1), 'state': 'open'})
            return self.env['hr.payslip'].create({
                'name': 'R', 'employee_id': empleado.id, 'contract_id': contrato.id,
                'company_id': company.id, 'struct_id': self.est.id,
                'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})

        ra, rb = recibo(self.a), recibo(self.b)
        vistas = []

        def capturar(recibos, *args, **kwargs):
            vistas.append((recibos.company_id.id, recibos.env.company.id))
            return True

        patron = 'odoo.addons.hr_payroll.models.hr_payslip.HrPayslip.compute_sheet'
        with mock.patch(patron, autospec=True, side_effect=capturar):
            (ra | rb).with_company(self.m).compute_sheet()
        self.assertEqual(sorted(vistas), sorted([(self.a.id, self.a.id), (self.b.id, self.b.id)]))
