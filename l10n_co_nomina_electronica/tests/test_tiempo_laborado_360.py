# -*- coding: utf-8 -*-
"""TiempoLaborado 360/30 (Anexo Tecnico DIAN §8.3.1, p.249; doc 53 §21.1). Funcion pura, valores a mano.
Uso previsto: inclusive=True (D19, David 2026-11-11: el dia de ingreso cuenta). NO esta conectada al XML.
Ademas, _ne_dias_bajo_contrato (nomina): ingreso el 10, el 16, febrero de 28 dias y mes de 31."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_co_nomina_electronica.services.dian_utils import (
    compute_worked_time, compute_worked_time_360 as f)


@tagged('post_install', '-at_install')
class TestTiempoLaborado360(TransactionCase):

    def test_ejemplo_oficial_anexo_inclusivo(self):
        # 5 anios + 3 meses + 18 dias = 5*360 + 3*30 + 18 = 1908; del 01-ene-2018 al 18-abr-2023, ambos incluidos.
        self.assertEqual(f(date(2018, 1, 1), date(2023, 4, 18), inclusive=True), 1908)
        self.assertEqual(f(date(2018, 1, 1), date(2023, 4, 19), inclusive=False), 1908)

    def test_caso_marzo_2024_a_marzo_2026_inclusivo(self):
        # 2 anios (720) + 0 meses + dias comerciales 1..30 (el 31 = 30) = 30 -> 750; el calendario daria 760.
        self.assertEqual(f(date(2024, 3, 1), date(2026, 3, 31), inclusive=True), 750)
        self.assertEqual(compute_worked_time(date(2024, 3, 1), date(2026, 3, 31)), 760)

    def test_ingreso_el_10_y_el_16_como_nomina(self):
        # mes de 31 dias, ingreso el 10: 10..30 = 21 (el 31 no suma); ingreso el 16: 16..30 = 15.
        self.assertEqual(f(date(2026, 3, 10), date(2026, 3, 31), inclusive=True), 21)
        self.assertEqual(f(date(2026, 3, 16), date(2026, 3, 31), inclusive=True), 15)
        self.assertEqual(f(date(2026, 3, 10), date(2026, 3, 15), inclusive=True), 6)

    def test_febrero_vale_30(self):
        self.assertEqual(f(date(2026, 2, 1), date(2026, 2, 28), inclusive=True), 30)
        self.assertEqual(f(date(2024, 2, 10), date(2024, 2, 29), inclusive=True), 21)
        # 28-feb (comercial 30) a 01-mar: 2 dias inclusivos
        self.assertEqual(f(date(2026, 2, 28), date(2026, 3, 1), inclusive=True), 2)

    def test_minimo_uno_y_cadenas(self):
        self.assertEqual(f(date(2026, 3, 1), date(2026, 3, 1), inclusive=False), 1)
        self.assertEqual(f(date(2026, 3, 1), date(2026, 3, 1), inclusive=True), 1)
        self.assertEqual(f('2026-01-01', '2026-01-15', inclusive=True), 15)
        self.assertEqual(f(None, date(2026, 1, 1), inclusive=True), 0)


@tagged('post_install', '-at_install')
class TestDiasBajoContratoIngreso(TransactionCase):
    """_ne_dias_bajo_contrato: dias comerciales del tramo con contrato vigente, ingreso inclusive."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía de Prueba Días Bajo Contrato',
            'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real'})
        structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Días Contrato', 'country_id': cls.env.ref('base.co').id})
        employee = cls.env['hr.employee'].create({
            'name': 'Empleado Días Contrato', 'company_id': cls.company.id,
            'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00',
            'l10n_co_ne_payment_method': '10'})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'Contrato Días Contrato', 'employee_id': employee.id,
            'company_id': cls.company.id, 'structure_type_id': structure_type.id,
            'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01',
            'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': date(2023, 1, 1), 'state': 'open'})
        cls.slip = cls.env['hr.payslip'].create({
            'name': 'Nómina Días Contrato', 'employee_id': employee.id,
            'contract_id': cls.contract.id, 'company_id': cls.company.id,
            'struct_id': cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina').id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})

    def _dias(self, ingreso, desde, hasta):
        self.contract.date_start = ingreso
        self.slip.write({'date_from': desde, 'date_to': hasta})
        return self.slip._ne_dias_bajo_contrato()

    def test_ingreso_el_10_marzo_mes_de_31(self):
        self.assertEqual(self._dias(date(2026, 3, 10), date(2026, 3, 10), date(2026, 3, 15)), 6)
        self.assertEqual(self._dias(date(2026, 3, 10), date(2026, 3, 16), date(2026, 3, 31)), 15)
        self.assertEqual(self._dias(date(2026, 3, 10), date(2026, 3, 1), date(2026, 3, 31)), 21)

    def test_ingreso_el_16(self):
        self.assertEqual(self._dias(date(2026, 3, 16), date(2026, 3, 1), date(2026, 3, 15)), 0)
        self.assertEqual(self._dias(date(2026, 3, 16), date(2026, 3, 16), date(2026, 3, 31)), 15)
        self.assertEqual(self._dias(date(2026, 3, 16), date(2026, 3, 1), date(2026, 3, 31)), 15)

    def test_febrero_28_dias(self):
        self.assertEqual(self._dias(date(2023, 1, 1), date(2026, 2, 1), date(2026, 2, 28)), 30)
        self.assertEqual(self._dias(date(2023, 1, 1), date(2026, 2, 16), date(2026, 2, 28)), 15)
        self.assertEqual(self._dias(date(2026, 2, 10), date(2026, 2, 1), date(2026, 2, 28)), 21)

    def test_mes_de_31_dias_completo(self):
        self.assertEqual(self._dias(date(2023, 1, 1), date(2026, 3, 1), date(2026, 3, 31)), 30)
        self.assertEqual(self._dias(date(2023, 1, 1), date(2026, 3, 16), date(2026, 3, 31)), 15)
