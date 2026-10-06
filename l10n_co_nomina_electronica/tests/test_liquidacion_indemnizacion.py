# -*- coding: utf-8 -*-
"""Regresión de la indemnización por despido sin justa causa (CO_LIQ_INDEMNIZACION, Art. 64
CST) -- Corrección 3 (AUD-DIAN-34, 2026-10-05): los días 30/20/20/15, el umbral de 10 SMMLV y
el piso de obra/labor pasaron de literales sueltos en la fórmula a hr.rule.parameter (David
confirmó los 6 valores, ninguno cambia). Estas pruebas fijan los MISMOS números que la fórmula
ya producía antes del cambio -- deben seguir dando exactamente lo mismo después.

Corre la regla real (hr_salary_rule_co_liq_indemnizacion) vía compute_sheet() sobre la
estructura real de Liquidación (hr_payroll_structure_co_liquidacion), no una reimplementación
en la prueba -- es la única forma de probar la fórmula real sin reinventarla aparte.
"""

from datetime import date, timedelta

from odoo.tests.common import TransactionCase


class TestLiquidacionIndemnizacion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía dedicada y descartable (ver AUD-DIAN-34 en test_dian_matching.py: la build
        # de Odoo.sh corre los tests sobre una COPIA de la BD real de Guapante).
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Indemnización',
        })
        co_country = cls.env['res.country'].search([('code', '=', 'CO')], limit=1)
        if not co_country:
            co_country = cls.env.ref('base.co')
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Liquidación',
            'country_id': co_country.id,
        })
        cls.liquidacion_struct = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.input_indemniz = cls.env.ref('l10n_co_nomina_electronica.input_co_liq_indemniz')
        # SMMLV 2026 (rule_parameter_smmlv_2026, data/l10n_co_rule_parameters_data.xml) --
        # todas las fechas de estas pruebas caen en 2026 para usar ese valor sin ambigüedad.
        cls.smmlv_2026 = 1750905.0

    def _make_contract(self, name, wage, date_start, contract_type='2'):
        employee = self.env['hr.employee'].create({
            'name': name,
            'identification_id': '50' + str(self.env['hr.employee'].search_count([])),
            'company_id': self.company.id,
            # l10n_co_ne_payment_method default es '1' (Transferencia Bancaria), que exige
            # l10n_co_ne_bank_account -- sin interés aquí, 'Efectivo' evita datos bancarios falsos.
            'l10n_co_ne_payment_method': '10',
        })
        contract = self.env['hr.contract'].create({
            'name': 'Contrato %s' % name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'date_start': date_start,
            'l10n_co_ne_contract_type': contract_type,
            'state': 'open',
        })
        return employee, contract

    def _make_liquidacion_payslip(self, employee, contract, date_to, dias_restantes=None):
        payslip = self.env['hr.payslip'].create({
            'name': 'Liquidación %s' % employee.name,
            'employee_id': employee.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'struct_id': self.liquidacion_struct.id,
            'date_from': date_to.replace(day=1),
            'date_to': date_to,
            'l10n_co_ne_liquidacion_cause': 'sin_justa_causa',
        })
        if dias_restantes is not None:
            self.env['hr.payslip.input'].create({
                'payslip_id': payslip.id,
                'input_type_id': self.input_indemniz.id,
                'code': 'CO_LIQ_INDEMNIZ',
                'amount': dias_restantes,
            })
        return payslip

    def _indemnizacion_total(self, payslip):
        payslip.compute_sheet()
        line = payslip.line_ids.filtered(lambda l: l.code == 'CO_LIQ_INDEMNIZACION')
        self.assertTrue(line, 'CO_LIQ_INDEMNIZACION no generó línea -- la causa de retiro '
                               'no activó la regla o compute_sheet() falló antes de llegar.')
        return line.total

    def test_indefinido_menor_10_smmlv_3_5_anios(self):
        """(a) 3,5 años, $3.000.000 -> 80 días = $8.000.000 (30 + 2,5x20). 1260 días exactos
        (días calendario inclusivos / 360) dan 3,5 años."""
        date_to = date(2026, 6, 30)
        date_start = date_to - timedelta(days=1259)  # (date_to - date_start).days + 1 = 1260
        employee, contract = self._make_contract('Indef3y6m', 3000000.0, date_start)
        payslip = self._make_liquidacion_payslip(employee, contract, date_to)
        self.assertAlmostEqual(self._indemnizacion_total(payslip), 8000000.0, places=2)

    def test_indefinido_menor_10_smmlv_menos_de_un_anio(self):
        """(a) Menos de 1 año: siempre 30 días completos, sin proporción dentro del primer año."""
        date_to = date(2026, 6, 30)
        date_start = date_to - timedelta(days=179)  # ~0.5 años
        employee, contract = self._make_contract('IndefMenosUnAnio', 3000000.0, date_start)
        payslip = self._make_liquidacion_payslip(employee, contract, date_to)
        valor_dia = 3000000.0 / 30
        self.assertAlmostEqual(self._indemnizacion_total(payslip), valor_dia * 30, places=2)

    def test_indefinido_exactamente_10_smmlv_usa_20_y_15(self):
        """(a) Salario EXACTAMENTE 10 SMMLV (umbral, no lo supera) -> tramo >= 10 SMMLV: 20
        días primer año + 15 por cada año adicional. 3 años exactos (1080 días)."""
        date_to = date(2026, 6, 30)
        date_start = date_to - timedelta(days=1079)  # 1080 días = 3 años exactos
        wage = self.smmlv_2026 * 10
        employee, contract = self._make_contract('Indef10Smmlv', wage, date_start)
        payslip = self._make_liquidacion_payslip(employee, contract, date_to)
        valor_dia = wage / 30
        esperado = valor_dia * 20 + valor_dia * 15 * 2  # 1 primer año + 2 adicionales
        self.assertAlmostEqual(self._indemnizacion_total(payslip), esperado, places=2)

    def test_termino_fijo_dias_restantes_sin_piso(self):
        """(a) Término fijo: paga exactamente los días restantes, sin piso de 15 días."""
        date_to = date(2026, 6, 30)
        employee, contract = self._make_contract(
            'Fijo', 3000000.0, date(2024, 1, 1), contract_type='1')
        payslip = self._make_liquidacion_payslip(employee, contract, date_to, dias_restantes=45)
        valor_dia = 3000000.0 / 30
        self.assertAlmostEqual(self._indemnizacion_total(payslip), valor_dia * 45, places=2)

    def test_obra_labor_por_debajo_del_piso_paga_15_dias(self):
        """(a) Obra/labor con menos de 15 días restantes -> paga el piso de 15 días, no los
        días reales (a diferencia de término fijo, que no tiene este piso)."""
        date_to = date(2026, 6, 30)
        employee, contract = self._make_contract(
            'ObraLabor', 3000000.0, date(2024, 1, 1), contract_type='3')
        payslip = self._make_liquidacion_payslip(employee, contract, date_to, dias_restantes=10)
        valor_dia = 3000000.0 / 30
        self.assertAlmostEqual(self._indemnizacion_total(payslip), valor_dia * 15, places=2)
