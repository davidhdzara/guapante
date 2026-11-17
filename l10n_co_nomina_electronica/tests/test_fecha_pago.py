# -*- coding: utf-8 -*-
"""Fecha de pago (doc 53 §20.3): ajuste de compania, accesor unico _ne_fechas_pago y accion Registrar pago."""

from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFechaPago(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Compañía Fecha Pago', 'country_id': cls.env.ref('base.co').id,
            'l10n_co_pila_tipo_aportante': '1', 'l10n_co_pila_forma_presentacion': 'U',
            'l10n_co_pila_clase_riesgo': '1', 'l10n_co_ne_febrero_modo': 'real'})
        structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Estructura Fecha Pago', 'country_id': cls.env.ref('base.co').id})
        employee = cls.env['hr.employee'].create({
            'name': 'Empleado Fecha Pago', 'company_id': cls.company.id, 'l10n_co_ne_worker_type': '01',
            'l10n_co_ne_worker_subtype': '00', 'l10n_co_ne_payment_method': '10'})
        contract = cls.env['hr.contract'].create({
            'name': 'Contrato Fecha Pago', 'employee_id': employee.id, 'company_id': cls.company.id,
            'structure_type_id': structure_type.id, 'l10n_co_ne_contract_type': '2',
            'l10n_co_pila_tipo_cotizante': '01', 'l10n_co_pila_subtipo_cotizante': '00',
            'wage': 3000000.0, 'date_start': date(2025, 1, 1), 'state': 'open'})
        struct = cls.env.ref('l10n_co_nomina_electronica.hr_payroll_structure_co_nomina')
        cls.slip = cls.env['hr.payslip'].create({
            'name': 'Recibo Fecha Pago', 'employee_id': employee.id, 'contract_id': contract.id,
            'company_id': cls.company.id, 'struct_id': struct.id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 15)})

    def _registrar(self, slips, fecha):
        return self.env['hr.payslip.registrar.pago'].create({'payslip_ids': [(6, 0, slips.ids)], 'fecha': fecha})

    # ── Accesor ──────────────────────────────────────────────────────
    def test_sin_fuente_error_claro(self):
        self.assertFalse(self.company.l10n_co_ne_fuente_fecha_pago)   # sin valor por defecto
        with self.assertRaisesRegex(UserError, 'fuente de la fecha de pago'):
            self.slip._ne_fechas_pago()

    def test_fuente_recibo(self):
        self.company.l10n_co_ne_fuente_fecha_pago = 'recibo'
        with self.assertRaisesRegex(UserError, 'no tiene fecha de pago'):
            self.slip._ne_fechas_pago()
        self.slip.paid_date = date(2026, 3, 16)
        self.assertEqual(self.slip._ne_fechas_pago(), [date(2026, 3, 16)])
        self.assertEqual(self.slip._ne_fecha_pago(), date(2026, 3, 16))

    def test_fuente_contabilidad_usa_pagos_conciliados(self):
        self.company.l10n_co_ne_fuente_fecha_pago = 'contabilidad'
        self.slip.paid_date = date(2026, 3, 1)   # el campo del recibo NO se mira en este modo
        with patch.object(type(self.slip), '_ne_fechas_pagos_contables',
                          lambda s: [date(2026, 3, 15), date(2026, 3, 20)]):
            self.assertEqual(self.slip._ne_fechas_pago(), [date(2026, 3, 15), date(2026, 3, 20)])
            self.assertEqual(self.slip._ne_fecha_pago(), date(2026, 3, 15))   # la primera define el mes
        with patch.object(type(self.slip), '_ne_fechas_pagos_contables', lambda s: []):
            with self.assertRaisesRegex(UserError, 'no tiene pagos conciliados'):
                self.slip._ne_fechas_pago()

    def test_fechas_contables_sin_asiento_es_vacio(self):
        self.assertFalse(self.slip.move_id)
        self.assertEqual(self.slip._ne_fechas_pagos_contables(), [])

    # ── Registrar pago ───────────────────────────────────────────────
    def test_registrar_pago_pone_la_fecha_elegida(self):
        self.company.l10n_co_ne_fuente_fecha_pago = 'recibo'
        self.slip.state = 'done'
        self._registrar(self.slip, date(2026, 3, 16)).action_registrar_pago()
        self.assertEqual(self.slip.state, 'paid')
        self.assertEqual(self.slip.paid_date, date(2026, 3, 16))   # no "hoy" del nativo

    def test_registrar_pago_valida(self):
        self.company.l10n_co_ne_fuente_fecha_pago = 'recibo'
        manana = fields.Date.context_today(self.slip) + timedelta(days=1)
        self.slip.state = 'done'
        with self.assertRaisesRegex(UserError, 'futura'):
            self._registrar(self.slip, manana).action_registrar_pago()
        self.slip.state = 'draft'
        with self.assertRaisesRegex(UserError, 'estado "Hecho"'):
            self._registrar(self.slip, date(2026, 3, 16)).action_registrar_pago()

    def test_registrar_pago_exige_fuente_recibo(self):
        self.slip.state = 'done'
        self.company.l10n_co_ne_fuente_fecha_pago = 'contabilidad'
        with self.assertRaisesRegex(UserError, 'no sale del recibo'):
            self._registrar(self.slip, date(2026, 3, 16)).action_registrar_pago()
        self.company.l10n_co_ne_fuente_fecha_pago = False
        with self.assertRaisesRegex(UserError, 'no sale del recibo'):
            self._registrar(self.slip, date(2026, 3, 16)).action_registrar_pago()
