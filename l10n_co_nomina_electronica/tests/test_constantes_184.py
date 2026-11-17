# -*- coding: utf-8 -*-
"""Filas 9 y 12 del doc 50 (.184): lote del cron de reconsulta como ir.config_parameter y provision de
vacaciones derivada de los parametros (salario x 30 / 720 = salario / 24)."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestConstantes184(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Empresa Constantes 184', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN',
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U'})

    def test_el_lote_del_cron_es_un_parametro_con_default_200(self):
        clave = 'l10n_co_nomina_electronica.recheck_batch_limit'
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param(clave), '200')
        self.assertEqual(self.company._ne_config_int_param(clave, 50), 200)
        self.env['ir.config_parameter'].sudo().set_param(clave, '3')
        self.assertEqual(self.company._ne_config_int_param(clave, 200), 3)

    def test_provision_de_vacaciones_es_un_veinticuatroavo_del_salario(self):
        """3.000.000 x 30 / 720 = 125.000 (= 3.000.000 / 24, el valor de la constante anterior)."""
        tipo = self.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Provision', 'country_id': self.env.ref('base.co').id})
        empleado = self.env['hr.employee'].create({
            'name': 'Emp Provision', 'company_id': self.company.id,
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00'})
        contrato = self.env['hr.contract'].create({
            'name': 'C', 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': tipo.id, 'wage': 3000000.0, 'date_start': date(2026, 1, 1),
            'state': 'open', 'l10n_co_ne_contract_type': '2',
            'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00'})
        recibo = self.env['hr.payslip'].create({
            'name': 'R', 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': self.company.id,
            'struct_id': self.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})
        regla = self.env.ref('l10n_co_nomina_electronica.hr_salary_rule_co_prov_vacaciones')
        resultado = regla._compute_rule({'payslip': recibo, 'contract': contrato})
        self.assertAlmostEqual(resultado[0], 125000.0, delta=0.01)
