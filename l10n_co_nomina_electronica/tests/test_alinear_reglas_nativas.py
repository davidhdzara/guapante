# -*- coding: utf-8 -*-
"""E-3a (doc 59 §20.2): las reglas nativas NET de nuestras estructuras dan el neto del modulo y `basic_wage` sale de la linea de sueldo del
modulo. Hallazgo H-QA-017: la columna «Salario basico» (nativa: paid_amount = salario mensual repartido entre las horas del periodo) solo
coincidia con CO_BASICO en periodos completos (Zapata, ingreso 12-jun: 318.346,36 vs 233.454,00). BASIC y GROSS nativas NO se tocan
(la categoria GROSS alimenta la base de la retencion en la fuente: doc 59 §20.3)."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAlinearReglasNativas(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Alinear Nativas'})
        cls.env = cls.company.with_company(cls.company).env
        cls.tipo = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_type_co')
        cls.general = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _regla_neto(self, xmlid):
        estructura = self.env.ref('l10n_co_nomina_electronica.%s' % xmlid)
        return estructura.with_context(active_test=False).rule_ids.filtered(lambda r: r.code == 'NET')

    def _recibo(self, ingreso, desde, hasta, wage=1750905.0):
        empleado = self.env['hr.employee'].create({
            'name': 'Empleado Alinear %s' % ingreso, 'company_id': self.company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contrato = self.env['hr.contract'].create({
            'name': 'Contrato Alinear %s' % ingreso, 'employee_id': empleado.id, 'company_id': self.company.id,
            'structure_type_id': self.tipo.id, 'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00', 'wage': wage, 'date_start': ingreso, 'state': 'open'})
        recibo = self.env['hr.payslip'].create({
            'name': 'Recibo Alinear %s' % desde, 'employee_id': empleado.id, 'contract_id': contrato.id,
            'company_id': self.company.id, 'struct_id': self.general.id, 'date_from': desde, 'date_to': hasta})
        recibo.compute_sheet()
        return recibo

    def _linea(self, recibo, codigo):
        return recibo.line_ids.filtered(lambda l: l.code == codigo).total

    def test_la_regla_neto_de_cada_estructura_lee_el_neto_del_modulo_y_va_despues_de_el(self):
        esperado = {'hr_payroll_structure_co_nomina': 'CO_NETO', 'hr_payroll_structure_co_liquidacion': 'CO_LIQ_NETO',
                    'hr_payroll_structure_co_prima': 'CO_PRIMA_NETO', 'hr_payroll_structure_co_bonificacion': 'CO_BON_NETO'}
        for xmlid, codigo in esperado.items():
            neto = self._regla_neto(xmlid)
            self.assertEqual(len(neto), 1, xmlid)
            self.assertIn("result_rules['%s']['total']" % codigo, neto.amount_python_compute)
            regla_modulo = neto.struct_id.with_context(active_test=False).rule_ids.filtered(lambda r: r.code == codigo)
            self.assertGreater(neto.sequence, regla_modulo.sequence, xmlid)

    def test_la_funcion_es_idempotente_y_respeta_una_formula_editada_a_mano(self):
        neto = self._regla_neto('hr_payroll_structure_co_nomina')
        antes = (neto.amount_python_compute, neto.sequence)
        self.env['hr.salary.rule']._ne_alinear_reglas_nativas()
        self.assertEqual((neto.amount_python_compute, neto.sequence), antes)
        neto.amount_python_compute = 'result = 12345'
        self.env['hr.salary.rule']._ne_alinear_reglas_nativas()
        self.assertEqual(neto.amount_python_compute, 'result = 12345')

    def test_el_neto_nativo_del_recibo_es_el_neto_del_modulo(self):
        recibo = self._recibo(date(2024, 1, 1), date(2026, 6, 1), date(2026, 6, 15))
        self.assertAlmostEqual(self._linea(recibo, 'NET'), self._linea(recibo, 'CO_NETO'), delta=0.01)
        self.assertAlmostEqual(recibo.net_wage, self._linea(recibo, 'CO_NETO'), delta=0.01)

    def test_salario_basico_de_un_periodo_parcial_es_el_de_la_linea_de_sueldo(self):
        """H-QA-017: ingreso 12-jun, quincena 1-15: 4 dias comerciales = 233.454,00 (no el paid_amount nativo)."""
        recibo = self._recibo(date(2026, 6, 12), date(2026, 6, 1), date(2026, 6, 15))
        sueldo = self._linea(recibo, 'CO_BASICO')
        self.assertAlmostEqual(sueldo, 233454.0, delta=0.01)
        self.assertAlmostEqual(recibo.basic_wage, sueldo, delta=0.01)

    def test_salario_basico_de_un_periodo_completo_no_cambia(self):
        recibo = self._recibo(date(2024, 1, 1), date(2026, 6, 1), date(2026, 6, 30))
        self.assertAlmostEqual(recibo.basic_wage, 1750905.0, delta=0.01)
