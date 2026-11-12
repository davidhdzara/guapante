# -*- coding: utf-8 -*-
"""Liquidacion con date_from distinto de contract.date_start (defecto hallado por QA, recibo 12954).

Las reglas de liquidacion que dependen del tramo contractual (vacaciones causadas/tomadas, tramo
pagable) asumen que el recibo va de inicio de contrato a retiro. Con otro date_from las
vacaciones de meses anteriores no se descontaban y el valor salia inflado SIN aviso. Debe fallar
con un UserError claro (recibo, fecha esperada, donde corregir); no se corrige en silencio.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

INGRESO = date(2025, 1, 1)
RETIRO = date(2026, 1, 2)


@tagged('post_install', '-at_install')
class TestLiquidacionInicioTramo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real',
            'l10n_co_ne_redondeo_dias': 'DOWN',
            'name': 'Compañía de Prueba Inicio Tramo Liquidación'})
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Inicio Tramo', 'country_id': cls.env.ref('base.co').id})
        cls.liquidacion = cls.env.ref(
            'l10n_co_nomina_electronica.hr_payroll_structure_co_liquidacion')
        cls.nomina = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Inicio Tramo', 'company_id': cls.company.id,
            'l10n_co_ne_payment_method': '10'})
        cls.contract = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Inicio Tramo', 'employee_id': employee.id,
            'company_id': cls.company.id, 'structure_type_id': cls.structure_type.id,
            'wage': 3000000.0, 'date_start': INGRESO, 'state': 'open'})

    def _recibo(self, struct, date_from, date_to=RETIRO):
        return self.env['hr.payslip'].create({
            'name': 'Liquidación Inicio Tramo', 'employee_id': self.contract.employee_id.id,
            'contract_id': self.contract.id, 'company_id': self.company.id,
            'struct_id': struct.id, 'date_from': date_from, 'date_to': date_to})

    def test_vacaciones_con_date_from_distinto_del_ingreso_falla_con_aviso(self):
        slip = self._recibo(self.liquidacion, date(2025, 12, 1))
        with self.assertRaises(UserError) as exc:
            slip._ne_liq_vacaciones_dias()
        msg = str(exc.exception)
        self.assertIn('Liquidación Inicio Tramo', msg)
        self.assertIn('2025-01-01', msg)

    def test_compute_sheet_falla_con_aviso_y_no_calcula_en_silencio(self):
        slip = self._recibo(self.liquidacion, date(2025, 12, 1))
        with self.assertRaises(UserError) as exc:
            slip.compute_sheet()
        self.assertIn('2025-01-01', str(exc.exception))

    def test_con_date_from_igual_al_ingreso_calcula(self):
        slip = self._recibo(self.liquidacion, INGRESO)
        slip.compute_sheet()
        self.assertTrue(slip.line_ids)

    def test_la_nomina_mensual_no_se_ve_afectada(self):
        slip = self._recibo(self.nomina, date(2025, 12, 1), date(2025, 12, 31))
        slip.compute_sheet()
        self.assertTrue(slip.line_ids)
