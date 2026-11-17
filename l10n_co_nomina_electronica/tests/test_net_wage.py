# -*- coding: utf-8 -*-
"""Salario neto / bruto nativos (2026-11-09, hallazgo de QA, decisión de Tech Lead): net_wage y
gross_wage deben reflejar CO_NETO / CO_BRUTO (y los netos de prima, liquidación y bonificación),
no el básico que calculan las reglas nativas BASIC/GROSS/NET por defecto.

Nivel de verificación (doc 38): pruebas del compute sobre la estructura real (general) y sobre
líneas de neto de las otras 3 estructuras; NO cubre el PDF nativo ni el export bancario, que solo
leen el campo.
"""

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNetWage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía de Prueba Net Wage'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Net Wage',
            'country_id': cls.env.ref('base.co').id,
        })
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')

    def _payslip(self, name='NetWage', wage=1800000.0):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id,
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'date_start': date(2024, 1, 1),
            'state': 'open',
        })
        return self.env['hr.payslip'].create({
            'name': 'Nómina %s' % name,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })

    def _linea(self, payslip, code):
        return payslip.line_ids.filtered(lambda l: l.code == code)

    def test_net_wage_es_co_neto_y_no_el_basico(self):
        payslip = self._payslip()
        payslip.compute_sheet()
        neto = self._linea(payslip, 'CO_NETO')
        basico = self._linea(payslip, 'CO_BASICO')
        self.assertTrue(neto and basico)
        self.assertAlmostEqual(payslip.net_wage, neto.total, delta=0.01)
        # con auxilio de transporte el neto real supera al básico: el campo nativo ya no
        # puede quedarse en el básico
        self.assertGreater(payslip.net_wage, basico.total)

    def test_gross_wage_es_co_bruto(self):
        payslip = self._payslip('Bruto')
        payslip.compute_sheet()
        bruto = self._linea(payslip, 'CO_BRUTO')
        self.assertTrue(bruto)
        self.assertAlmostEqual(payslip.gross_wage, bruto.total, delta=0.01)

    def test_sin_linea_de_neto_conserva_el_calculo_nativo(self):
        """Un recibo de una estructura sin ninguna regla de neto propia no se altera."""
        estructura = self.env['hr.payroll.structure'].create({
            'name': 'Estructura sin neto propio (prueba)', 'type_id': self.structure_type.id,
        })
        payslip = self._payslip('SinNeto')
        payslip.struct_id = estructura
        payslip.compute_sheet()
        self.assertFalse(self._linea(payslip, 'CO_NETO'))
        # el valor sale del cálculo nativo (línea NET); no se fuerza a otro número
        nativo = self._linea(payslip, 'NET')
        self.assertAlmostEqual(payslip.net_wage, sum(nativo.mapped('total')), delta=0.01)

    def test_netos_de_prima_liquidacion_y_bonificacion(self):
        for code in ('CO_PRIMA_NETO', 'CO_LIQ_NETO', 'CO_BON_NETO'):
            regla = self.env['hr.salary.rule'].search([('code', '=', code)], limit=1)
            self.assertTrue(regla, 'Falta la regla %s' % code)
            payslip = self._payslip('Neto %s' % code)
            self.env['hr.payslip.line'].create({
                'slip_id': payslip.id, 'salary_rule_id': regla.id, 'code': code,
                'name': code, 'contract_id': payslip.contract_id.id,
                'employee_id': payslip.employee_id.id,
                'quantity': 1.0, 'rate': 100.0, 'amount': 777000.0,
                # hr.payslip.line.total es un Monetary plano, NO computado: lo escribe el motor
                # de reglas en compute_sheet(); al crear la línea a mano hay que dárselo.
                'total': 777000.0,
            })
            # Se fuerza el recálculo de net_wage por claridad (la causa del 0.0 era el total de
            # la línea, no el disparador de dependencias).
            payslip.env.add_to_compute(payslip._fields['net_wage'], payslip)
            self.assertAlmostEqual(
                payslip.net_wage, 777000.0, delta=0.01,
                msg='%s | líneas: %s' % (code, [
                    (l.code, l.total) for l in payslip.line_ids]))
