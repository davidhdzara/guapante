# -*- coding: utf-8 -*-
"""Recibos solapados: confirmar un recibo cuyo periodo se cruza con otro confirmado del
mismo empleado y la misma estructura es error; otras estructuras, ajustes y periodos
contiguos se permiten. Se prueba _ne_validar_sin_solape() (lo que llama action_payslip_done)
con estados fijados directo, para no depender de la contabilidad."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRecibosSolapados(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U', 'country_id': cls.env.ref('base.co').id, 'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real', 'l10n_co_ne_redondeo_dias': 'DOWN', 'name': 'Compañía Prueba Solapes'})
        cls.env = cls.company.with_company(cls.company).env
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Prueba Estructura Solapes', 'country_id': cls.env.ref('base.co').id})
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Nómina Solapes A', 'type_id': cls.structure_type.id})
        cls.otra_estructura = cls.env['hr.payroll.structure'].create({
            'name': 'Prima Solapes B', 'type_id': cls.structure_type.id})
        cls.employee = cls.env['hr.employee'].create({'l10n_co_ne_worker_type': '01', 'l10n_co_ne_worker_subtype': '00', 
            'name': 'Luis Mora', 'company_id': cls.company.id,
            'l10n_co_ne_payment_method': '10'})
        cls.contract = cls.env['hr.contract'].create({'l10n_co_ne_contract_type': '2', 'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00', 
            'name': 'Contrato Solapes', 'employee_id': cls.employee.id,
            'company_id': cls.company.id, 'structure_type_id': cls.structure_type.id,
            'wage': 3000000.0, 'date_start': date(2024, 1, 1), 'state': 'open'})

    def _recibo(self, ini, fin, estado='draft', struct=None, **extra):
        return self.env['hr.payslip'].create({
            'name': 'Recibo %s' % ini, 'employee_id': self.employee.id,
            'contract_id': self.contract.id, 'company_id': self.company.id,
            'struct_id': (struct or self.structure).id,
            'date_from': ini, 'date_to': fin, 'state': estado, **extra})

    def test_cruce_misma_estructura_es_error_y_nombra_al_otro(self):
        existente = self._recibo(date(2026, 9, 1), date(2026, 9, 30), 'done')
        nuevo = self._recibo(date(2026, 9, 15), date(2026, 10, 15))
        with self.assertRaises(UserError) as ctx:
            nuevo._ne_validar_sin_solape()
        self.assertIn(existente.name, str(ctx.exception))

    def test_cruce_con_pagado_tambien_es_error(self):
        self._recibo(date(2026, 9, 1), date(2026, 9, 30), 'paid')
        with self.assertRaises(UserError):
            self._recibo(date(2026, 9, 30), date(2026, 9, 30))._ne_validar_sin_solape()

    def test_otra_estructura_se_permite(self):
        self._recibo(date(2026, 9, 1), date(2026, 9, 30), 'done')
        self._recibo(date(2026, 9, 1), date(2026, 9, 30), struct=self.otra_estructura
                     )._ne_validar_sin_solape()

    def test_periodos_contiguos_se_permiten(self):
        self._recibo(date(2026, 9, 1), date(2026, 9, 30), 'done')
        self._recibo(date(2026, 10, 1), date(2026, 10, 31))._ne_validar_sin_solape()

    def test_nota_de_ajuste_se_permite(self):
        self._recibo(date(2026, 9, 1), date(2026, 9, 30), 'done')
        ajuste = self._recibo(
            date(2026, 9, 1), date(2026, 9, 30), l10n_co_ne_is_adjustment=True,
            l10n_co_ne_adjustment_ref_cune='CUNE-ORIGINAL')
        ajuste._ne_validar_sin_solape()

    def test_recibo_cancelado_o_borrador_no_cuenta(self):
        self._recibo(date(2026, 9, 1), date(2026, 9, 30), 'cancel')
        self._recibo(date(2026, 9, 1), date(2026, 9, 30), 'draft')
        self._recibo(date(2026, 9, 10), date(2026, 9, 20))
        # el borrador de arriba no es 'done': no hay conflicto con ellos
        self.env['hr.payslip'].search([('state', '=', 'draft')])[-1]._ne_validar_sin_solape()

    def test_lote_con_dos_solapados_es_error(self):
        a = self._recibo(date(2026, 9, 1), date(2026, 9, 20))
        b = self._recibo(date(2026, 9, 15), date(2026, 9, 30))
        with self.assertRaises(UserError):
            (a | b)._ne_validar_sin_solape()

    def test_lote_sin_solape_pasa(self):
        a = self._recibo(date(2026, 9, 1), date(2026, 9, 15))
        b = self._recibo(date(2026, 9, 16), date(2026, 9, 30))
        (a | b)._ne_validar_sin_solape()
