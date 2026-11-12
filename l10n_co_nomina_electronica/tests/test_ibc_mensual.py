# -*- coding: utf-8 -*-
"""Consolidacion mensual del IBC (H-017b, commit 3b): una funcion pura del conjunto de
recibos confirmados del empleado en el mes; independiente del orden de confirmacion;
PILA incluye recibos 'paid' y liquidaciones (se filtra por date_to).

Nivel de verificacion: _refrescar sobre recibos reales calculados con compute_sheet (el
estado 'done' se fija directo para no depender de la contabilidad); el archivo PILA
completo y el reporte UGPP en Excel se prueban en servidor."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestIbcMensual(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba IBC Mensual'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura IBC Mensual', 'country_id': cls.env.ref('base.co').id})
        cls.structure = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.Consolidado = cls.env['l10n.co.ibc.mensual']

    def _empleado(self, name, wage):
        employee = self.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': name, 'company_id': self.company.id, 'l10n_co_ne_payment_method': '10'})
        contract = self.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato %s' % name, 'employee_id': employee.id,
            'company_id': self.company.id, 'structure_type_id': self.structure_type.id,
            'wage': wage, 'date_start': date(2024, 1, 1), 'state': 'open'})
        return employee, contract

    def _recibo(self, employee, contract, ini, fin):
        slip = self.env['hr.payslip'].create({
            'name': 'Nómina %s' % employee.name, 'employee_id': employee.id,
            'contract_id': contract.id, 'company_id': self.company.id,
            'struct_id': self.structure.id, 'date_from': ini, 'date_to': fin})
        slip.compute_sheet()
        return slip

    def _confirmar(self, *slips):
        for s in slips:
            s.state = 'done'
        slips[0]._ne_refrescar_ibc_mensual()

    def test_un_solo_recibo_el_consolidado_es_igual_al_recibo(self):
        employee, contract = self._empleado('Uno', 3000000.0)
        slip = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._confirmar(slip)
        cons = self.Consolidado.search([('employee_id', '=', employee.id)])
        self.assertEqual(len(cons), 1)
        ibc = slip.line_ids.filtered(lambda l: l.code == 'CO_IBC_SP').total
        self.assertAlmostEqual(cons.ibc_sp, ibc, delta=0.01)
        self.assertAlmostEqual(cons.diferencia_sp, 0.0, delta=0.01)
        self.assertEqual(cons.dias_sp, 30)

    def test_dos_recibos_el_techo_se_aplica_sobre_la_suma(self):
        employee, contract = self._empleado('Dos', 80000000.0)
        a = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 15))
        b = self._recibo(employee, contract, date(2026, 9, 16), date(2026, 9, 30))
        self._confirmar(a, b)
        cons = self.Consolidado.search([('employee_id', '=', employee.id)])
        smmlv = a._rule_parameter('l10n_co_smmlv', a.date_from)
        self.assertAlmostEqual(cons.ibc_sp, 25 * smmlv, delta=0.01)
        self.assertEqual(cons.dias_sp, 30)
        # cada recibo, por separado, ya estaba bajo el techo: la diferencia queda auditable
        self.assertLess(cons.diferencia_sp, 0.0)
        self.assertEqual(len(cons.payslip_ids), 2)

    def test_independiente_del_orden_de_confirmacion(self):
        employee, contract = self._empleado('Orden', 80000000.0)
        a = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 15))
        b = self._recibo(employee, contract, date(2026, 9, 16), date(2026, 9, 30))
        b.state = 'done'
        b._ne_refrescar_ibc_mensual()
        parcial = self.Consolidado.search([('employee_id', '=', employee.id)]).ibc_sp
        a.state = 'done'
        a._ne_refrescar_ibc_mensual()
        orden_1 = self.Consolidado.search([('employee_id', '=', employee.id)]).ibc_sp
        # reiniciar y confirmar en el orden inverso
        a.state = b.state = 'draft'
        a._ne_refrescar_ibc_mensual()
        self.assertFalse(self.Consolidado.search([('employee_id', '=', employee.id)]))
        a.state = 'done'
        a._ne_refrescar_ibc_mensual()
        b.state = 'done'
        b._ne_refrescar_ibc_mensual()
        orden_2 = self.Consolidado.search([('employee_id', '=', employee.id)]).ibc_sp
        self.assertAlmostEqual(orden_1, orden_2, delta=0.01)
        self.assertNotAlmostEqual(parcial, orden_1, delta=1.0)  # el parcial si era distinto

    def test_volver_a_borrador_elimina_el_consolidado(self):
        employee, contract = self._empleado('Borrador', 3000000.0)
        slip = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 30))
        self._confirmar(slip)
        slip.state = 'draft'
        slip._ne_refrescar_ibc_mensual()
        self.assertFalse(self.Consolidado.search([('employee_id', '=', employee.id)]))

    def test_pila_incluye_pagados_y_filtra_por_date_to(self):
        employee, contract = self._empleado('Pila', 3000000.0)
        estructura = self.structure
        # Recibo normal pagado
        normal = self.env['hr.payslip'].create({
            'name': 'Nómina Pila', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': estructura.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30), 'state': 'paid'})
        # Tipo liquidacion: date_from = inicio de contrato, date_to en el mes (creado ya
        # con sus fechas: mutar date_from de un recibo existente dispara recalculo nativo)
        liquidacion = self.env['hr.payslip'].create({
            'name': 'Liquidación Pila', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': self.company.id, 'struct_id': estructura.id,
            'date_from': date(2024, 1, 1), 'date_to': date(2026, 9, 20), 'state': 'done'})
        wizard = self.env['l10n.co.hr.pila.wizard.v2']
        encontrados = wizard._get_period_payslips(self.company, 2026, 9)
        self.assertIn(normal, encontrados)
        self.assertIn(liquidacion, encontrados)

    def test_integral_en_dos_recibos_suma_un_solo_ibc(self):
        employee, contract = self._empleado('Integral', 20000000.0)
        contract.l10n_co_ne_integral_salary = True
        a = self._recibo(employee, contract, date(2026, 9, 1), date(2026, 9, 15))
        b = self._recibo(employee, contract, date(2026, 9, 16), date(2026, 9, 30))
        self._confirmar(a, b)
        cons = self.Consolidado.search([('employee_id', '=', employee.id)])
        factor = a._rule_parameter('l10n_co_factor_integral_salary', a.date_from)
        # 70% del integral UNA vez (cada recibo aporta la mitad), no el doble
        self.assertAlmostEqual(cons.ibc_sp, 20000000.0 * factor, delta=1.0)
        self.assertEqual(cons.dias_sp, 30)
